# CreditBridge Demo Credentials

## 🔐 Bank Staff Portal

**URL:** `http://localhost:5000/bank/login`

---

## Login Credentials

| ID | Password | Role | Branch |
|----|----------|------|--------|
| `admin` | `pass123` | Head of Bank | All |
| `manager1` | `pass123` | Branch Manager | Mumbai Downtown |
| `manager2` | `pass123` | Branch Manager | Andheri West |
| `credit` | `pass123` | Credit Manager | All |
| `loan1` | `pass123` | Loan Officer | Mumbai Downtown |
| `loan2` | `pass123` | Loan Officer | Andheri West |
| `analyst1` | `pass123` | Credit Analyst | Mumbai Downtown |
| `analyst2` | `pass123` | Credit Analyst | Andheri West |

---

## Organization Hierarchy

```
👑 HEAD OF BANK (admin)
   │
   ├── 🏢 BRANCH MANAGER (manager1, manager2)
   │       └── Full control of their branch
   │
   └── 📊 CREDIT MANAGER (credit)
           │
           ├── 💼 LOAN OFFICER (loan1, loan2)
           │       └── Creates loan applications
           │
           └── 🔍 CREDIT ANALYST (analyst1, analyst2)
                   └── Reviews & analyzes applications
```

---

## Complete Permission Breakdown

### 👑 HEAD OF BANK (`admin`)
> **Super Admin** - Complete system control across all branches

| Category | Permissions |
|----------|-------------|
| **Core** | `SUPER_ADMIN`, `ALL` - Bypass all permission checks |
| **View** | All branches, assessments, customers, employees, audit logs, system logs |
| **Edit** | Any assessment, override any decision, delete any record |
| **Manage** | Branches, employees, credit policies, system settings, ML model |
| **Reports** | Executive dashboard, comparative analytics, fraud reports, revenue analytics |
| **Critical** | Approve high-value loans (>₹75L), emergency override, purge data |
| **Create** | `CREATE_ASSESSMENT` ✅ |

**Why HOB can create assessments:** As super admin, HOB can perform ANY action including creating assessments for demonstration, testing, or emergency situations.

---

### 🏢 BRANCH MANAGER (`manager1`, `manager2`)
> **Full Branch Control** - Manages all operations within their branch

| Category | Permissions |
|----------|-------------|
| **Core** | `ALL` - Full access within branch |
| **View** | Branch assessments, customers, employees, analytics, audit logs |
| **Edit** | Create/edit/delete any assessment in branch, override decisions, reassign |
| **Team** | Manage employees, add/edit/deactivate staff, assign teams, set targets |
| **Approve** | High-risk loans (score <550), medium-value loans (₹37.5L-₹75L), policy exceptions |
| **Reports** | Export all/branch reports, view team performance, portfolio risk |
| **Config** | Branch settings, targets, bulk approve |
| **Create** | `CREATE_ASSESSMENT` ✅ |

**Why BM can create assessments:** Branch managers have `ALL` permission for their branch, enabling them to create assessments when loan officers are unavailable or for VIP customers.

---

### 📊 CREDIT MANAGER (`credit`)
> **Review & Quality Control** - Supervises loan officers and analysts

| Category | Permissions |
|----------|-------------|
| **View** | Team assessments, customers, performance, portfolio analytics |
| **Edit** | Team assessments, add review notes |
| **Decisions** | Approve assessments, reject assessments, recommend override |
| **Quality** | View escalations, review analyst work, reassign assessments, flag issues |
| **Team** | View analyst workload, assign assessments, mentor analysts |
| **Reports** | Export team reports, view approval trends |
| **Create** | `CREATE_ASSESSMENT` ✅ |

**Why CM can create assessments:** Credit managers may need to create assessments for training purposes, handle special cases, or assist when loan officers are overloaded.

---

### 💼 LOAN OFFICER (`loan1`, `loan2`)
> **Customer-Facing** - Primary creator of loan applications

| Category | Permissions |
|----------|-------------|
| **Create** | `CREATE_ASSESSMENT` ✅ - **Primary job function** |
| **View** | Own assessments, own customers, own performance |
| **Edit** | Own drafts only, upload documents, update customer info |
| **Workflow** | Submit for review, resubmit rejected, request reassignment, add notes |
| **Customer** | View assessment status, download PDF, send notifications |

**Why LO can create assessments:** This is their PRIMARY JOB FUNCTION. Loan officers are the front-line staff who meet customers and create loan applications.

---

### 🔍 CREDIT ANALYST (`analyst1`, `analyst2`)
> **Risk Specialist** - Analyzes and reviews applications

| Category | Permissions |
|----------|-------------|
| **View** | Assigned assessments only, assigned customers, advanced analytics |
| **Edit** | Assigned assessments (pending/under_review), add analysis notes, add fraud flags |
| **Analysis** | Mark under review, complete analysis, recommend approval/rejection/escalation |
| **Tools** | Fraud detection, document verification, behavioral analytics, custom analysis |
| **Workflow** | Submit review, flag fraud, escalate to manager, verify documents |
| **Create** | ❌ **Cannot create assessments** |

**Why Analyst CANNOT create assessments:** Credit analysts are risk specialists who REVIEW applications - they don't interact with customers. Creating assessments would violate separation of duties (the person analyzing shouldn't be the one creating).

---

## Navigation Access by Role

| Page | HOB | BM | CM | LO | Analyst |
|------|-----|----|----|----|----|
| Dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
| New Assessment | ✅ | ✅ | ✅ | ✅ | ❌ |
| Applications | ✅ | ✅ | ❌ | ❌ | ❌ |
| Customers | ✅ | ✅ | ❌ | ❌ | ❌ |
| Analytics | ✅ | ✅ | ❌ | ❌ | ❌ |
| Team Management | ✅ | ✅ | ❌ | ❌ | ❌ |
| Audit Logs | ✅ | ✅ | ❌ | ❌ | ❌ |
| Escalations | ✅ | ✅ | ✅ | ❌ | ❌ |
| Assigned Queue | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Workflow: Who Does What?

```
CUSTOMER arrives → LOAN OFFICER creates assessment
                            ↓
                   CREDIT ANALYST reviews & analyzes
                            ↓
                   CREDIT MANAGER approves/rejects
                            ↓
            (if high-value) BRANCH MANAGER final approval
                            ↓
            (if exception)  HEAD OF BANK override
```

---

## 🌐 Public Portal

**URL:** `http://localhost:5000/`

No login required - customers can check their credit score.

---

**⚠️ Demo credentials only - change before production!**
