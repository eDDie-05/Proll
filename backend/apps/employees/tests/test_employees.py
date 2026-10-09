from decimal import Decimal as D

import pytest

from apps.core.models import AuditLog
from apps.employees.models import Employee, SalaryRecord

pytestmark = pytest.mark.django_db


def payload(org, **kw):
    data = {
        "employee_number": "brv0100", "first_name": "Asha", "last_name": "Mushi", "department": org["dept"].id,
        "employment_type": org["etype"].id, "employment_start_date": "2026-01-01", "bank_name": "NMB",
        "bank_account_number": "22110000111", "tin": "123-456-789", "social_security_number": "NSSF-1",
    }
    data.update(kw)
    return data


def test_hr_crud_and_audit(make_user, client_for, org):
    hr = client_for(make_user("HR_MANAGER", "hr"))
    r = hr.post("/api/employees/", payload(org), format="json")
    assert r.status_code == 201, r.data
    assert r.data["employee_number"] == "BRV0100"
    eid = r.data["id"]
    assert AuditLog.objects.filter(action="CREATE", model="employees.Employee", object_id=str(eid)).exists()
    r = hr.patch(f"/api/employees/{eid}/", {"phone": "+255 712 000 000"}, format="json")
    assert r.status_code == 200
    log = AuditLog.objects.filter(action="UPDATE", model="employees.Employee", object_id=str(eid)).latest("id")
    assert log.old_values == {"phone": ""} and log.new_values == {"phone": "+255 712 000 000"}
    assert hr.delete(f"/api/employees/{eid}/").status_code == 400  # never hard-deleted


def test_employee_id_unique(make_user, client_for, org):
    hr = client_for(make_user("HR_MANAGER", "hr"))
    assert hr.post("/api/employees/", payload(org), format="json").status_code == 201
    assert hr.post("/api/employees/", payload(org), format="json").status_code == 400


def test_required_fields_and_dates(make_user, client_for, org):
    hr = client_for(make_user("HR_MANAGER", "hr"))
    r = hr.post("/api/employees/", {"first_name": "x"}, format="json")
    assert r.status_code == 400 and "last_name" in r.data and "department" in r.data
    r = hr.post("/api/employees/", payload(org, employment_end_date="2025-01-01"), format="json")
    assert r.status_code == 400
    r = hr.post("/api/employees/", payload(org, bank_account_number=""), format="json")
    assert r.status_code == 400 and "bank_account_number" in r.data


def test_sensitive_fields_hidden_from_manager(make_user, client_for, make_employee):
    make_employee(1_000_000, tin="999")
    mgr = client_for(make_user("MANAGER", "mgr"))
    row = mgr.get("/api/employees/").data["results"][0]
    for f in ("tin", "bank_account_number", "social_security_number", "date_of_birth"):
        assert f not in row
    hr = client_for(make_user("HR_MANAGER", "hr"))
    assert hr.get("/api/employees/").data["results"][0]["tin"] == "999"
    assert mgr.post("/api/employees/", {}, format="json").status_code == 403


def test_employee_cannot_access_directory(make_user, client_for, make_employee):
    u = make_user("EMPLOYEE", "emp")
    make_employee(1_000_000, user=u)
    c = client_for(u)
    assert c.get("/api/employees/").status_code == 403
    me = c.get("/api/self/profile/")
    assert me.status_code == 200 and me.data["current_basic_salary"] == "1000000.00"
    assert len(c.get("/api/self/salary-history/").data) == 1


def test_salary_history_append_only(make_user, client_for, make_employee):
    emp = make_employee(1_500_000)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    r = hr.post("/api/salaries/", {"employee": emp.id, "basic_salary": "1800000", "effective_from": "2027-01-01",
                                   "reason": "Annual review"}, format="json")
    assert r.status_code == 201, r.data
    assert hr.post("/api/salaries/", {"employee": emp.id, "basic_salary": "-1", "effective_from": "2027-02-01"},
                   format="json").status_code == 400
    sid = r.data["id"]
    assert hr.patch(f"/api/salaries/{sid}/", {"basic_salary": "1"}, format="json").status_code == 405
    assert hr.delete(f"/api/salaries/{sid}/").status_code == 405
    hist = hr.get(f"/api/employees/{emp.id}/salary-history/").data
    assert [h["basic_salary"] for h in hist] == ["1800000.00", "1500000.00"]
    assert hist[1]["effective_to"] == "2026-12-31"


def test_inactive_employee_salary_rejected(make_user, client_for, make_employee):
    emp = make_employee(1_000_000, status=Employee.Status.TERMINATED)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    r = hr.post("/api/salaries/", {"employee": emp.id, "basic_salary": "1", "effective_from": "2027-01-01"}, format="json")
    assert r.status_code == 400


def test_contract_history_and_salary_creation(make_user, client_for, make_employee, org):
    emp = make_employee(None)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    base = {"employee": emp.id, "employment_type": org["etype"].id, "department": org["dept"].id,
            "basic_salary": "900000", "status": "ACTIVE"}
    r1 = hr.post("/api/contracts/", {**base, "contract_number": "C-1", "start_date": "2026-01-01",
                                     "end_date": "2026-12-31", "create_salary_record": True}, format="json")
    assert r1.status_code == 201, r1.data
    r2 = hr.post("/api/contracts/", {**base, "contract_number": "C-2", "start_date": "2027-01-01", "basic_salary": "1100000",
                                     "create_salary_record": True}, format="json")
    assert r2.status_code == 201
    assert emp.contracts.count() == 2
    assert list(SalaryRecord.objects.filter(employee=emp).order_by("effective_from").values_list("basic_salary", flat=True)) == [
        D("900000"), D("1100000")]
    assert hr.delete(f"/api/contracts/{r1.data['id']}/").status_code == 400


def test_contract_upload_rejects_fake_pdf(make_user, client_for, make_employee, org):
    from django.core.files.uploadedfile import SimpleUploadedFile

    emp = make_employee(None)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    fake = SimpleUploadedFile("contract.pdf", b"MZ\x90\x00 not a pdf", content_type="application/pdf")
    r = hr.post("/api/contracts/", {"employee": emp.id, "employment_type": org["etype"].id, "department": org["dept"].id,
                                    "basic_salary": "1", "contract_number": "C-9", "start_date": "2026-01-01",
                                    "document": fake}, format="multipart")
    assert r.status_code == 400 and "document" in r.data
    exe = SimpleUploadedFile("contract.exe", b"MZ", content_type="application/octet-stream")
    r = hr.post("/api/contracts/", {"employee": emp.id, "employment_type": org["etype"].id, "department": org["dept"].id,
                                    "basic_salary": "1", "contract_number": "C-9", "start_date": "2026-01-01",
                                    "document": exe}, format="multipart")
    assert r.status_code == 400


def test_allowance_and_deduction_validation(make_user, client_for, make_employee):
    emp = make_employee(1_000_000)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    t = hr.post("/api/allowance-types/", {"code": "HOUSE", "name": "Housing", "is_taxable": True,
                                          "is_social_security_base": True}, format="json")
    assert t.status_code == 201, t.data
    # tax treatment must be stated explicitly
    assert hr.post("/api/allowance-types/", {"code": "X", "name": "X"}, format="json").status_code == 400
    r = hr.post("/api/employee-allowances/", {"employee": emp.id, "allowance_type": t.data["id"], "amount": "-5",
                                              "effective_from": "2026-01-01"}, format="json")
    assert r.status_code == 400
    d = hr.post("/api/deduction-types/", {"code": "INS", "name": "Insurance", "default_amount": "10000"}, format="json")
    assert d.status_code == 201
    r = hr.post("/api/employee-deductions/", {"employee": emp.id, "deduction_type": d.data["id"],
                                              "start_date": "2026-05-01", "end_date": "2026-04-01"}, format="json")
    assert r.status_code == 400


def test_loan_approval_segregation(make_user, client_for, make_employee):
    emp = make_employee(1_000_000)
    hr1 = client_for(make_user("HR_MANAGER", "hr1"))
    hr2 = client_for(make_user("HR_MANAGER", "hr2"))
    r = hr1.post("/api/loans/", {"employee": emp.id, "reference": "L1", "principal": "300000", "interest_rate": "10",
                                 "installment_amount": "110000", "number_of_installments": 3, "start_date": "2026-09-01"},
                 format="json")
    assert r.status_code == 201, r.data
    assert r.data["total_repayable"] == "330000.00"
    loan_id = Employee.objects.get(pk=emp.id).loans.get(reference="L1").id
    assert hr1.post(f"/api/loans/{loan_id}/approve/").status_code == 400
    assert hr2.post(f"/api/loans/{loan_id}/approve/").data["status"] == "ACTIVE"


def test_loan_installments_must_cover_total(make_user, client_for, make_employee):
    emp = make_employee(1_000_000)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    r = hr.post("/api/loans/", {"employee": emp.id, "reference": "L1", "principal": "300000", "interest_rate": "10",
                                "installment_amount": "110000", "number_of_installments": 3, "start_date": "2026-09-01"},
                format="json")
    assert r.status_code == 201
    r = hr.post("/api/loans/", {"employee": emp.id, "reference": "L3", "principal": "300000",
                                "installment_amount": "50000", "number_of_installments": 3, "start_date": "2026-09-01"},
                format="json")
    assert r.status_code == 400


def test_contract_document_served_only_through_api(make_user, client_for, make_employee, org, settings, tmp_path):
    from django.core.files.uploadedfile import SimpleUploadedFile

    settings.MEDIA_ROOT = tmp_path
    emp = make_employee(None)
    hr = client_for(make_user("HR_MANAGER", "hr"))
    pdf = SimpleUploadedFile("c.pdf", b"%PDF-1.4 test", content_type="application/pdf")
    r = hr.post("/api/contracts/", {"employee": emp.id, "employment_type": org["etype"].id, "department": org["dept"].id,
                                    "basic_salary": "1", "contract_number": "C-10", "start_date": "2026-01-01",
                                    "document": pdf}, format="multipart")
    assert r.status_code == 201, r.data
    assert r.data["document"] is True and "media" not in str(r.data)
    resp = hr.get(f"/api{r.data['document_url']}")
    assert resp.status_code == 200 and b"".join(resp.streaming_content).startswith(b"%PDF")
    assert client_for(make_user("MANAGER", "mgr")).get(f"/api{r.data['document_url']}").status_code == 403
