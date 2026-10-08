"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Briefcase, FileText, Plus, RefreshCw, Sparkles, UserRound } from "lucide-react";
import { api } from "@/lib/api";

interface RecruitmentRole {
  role_id: string;
  title: string;
  description: string;
  requirements: string;
  status: "OPEN" | "CLOSED";
  created_at: string;
}

interface Evidence {
  requirement: string;
  quote: string;
  assessment: string;
}

interface CandidateApplication {
  application_id: string;
  role_id: string;
  applicant_name: string | null;
  applicant_email: string | null;
  resume_filename: string;
  status: "READY" | "EVALUATED";
  screening_score: number | null;
  screening_summary: string | null;
  matched_requirements: string[];
  evidence: Evidence[];
  interview_email_subject: string | null;
  interview_email_body: string | null;
  created_at: string;
}

export default function RecruitmentPage() {
  const [roles, setRoles] = useState<RecruitmentRole[]>([]);
  const [applications, setApplications] = useState<CandidateApplication[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [selectedApplicationId, setSelectedApplicationId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [requirements, setRequirements] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [applicantName, setApplicantName] = useState("");
  const [applicantEmail, setApplicantEmail] = useState("");
  const [interviewDetails, setInterviewDetails] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadData = useCallback(async (preferredRoleId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const roleRows = await api.getRecruitmentRoles();
      if (!Array.isArray(roleRows)) throw new Error("Recruitment roles returned an unexpected response.");
      setRoles(roleRows);
      const activeRoleId = preferredRoleId ?? roleRows[0]?.role_id ?? "";
      setSelectedRoleId(activeRoleId);
      const candidateRows = await api.getCandidateApplications(activeRoleId || undefined);
      if (!Array.isArray(candidateRows)) {
        throw new Error("Candidate applications returned an unexpected response.");
      }
      setApplications(candidateRows);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load recruitment data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleCreateRole = async (event: FormEvent) => {
    event.preventDefault();
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createRecruitmentRole({
        title: title.trim(),
        description: description.trim(),
        requirements: requirements.trim(),
      });
      setTitle("");
      setDescription("");
      setRequirements("");
      setSelectedApplicationId("");
      setNotice("Job opening created.");
      await loadData(created.role_id);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Could not create the job opening.");
    } finally {
      setWorking(false);
    }
  };

  const handleUploadResume = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedRoleId || !resumeFile) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      const formData = new FormData();
      formData.append("resume", resumeFile);
      formData.append("applicant_name", applicantName.trim());
      formData.append("applicant_email", applicantEmail.trim());
      await api.uploadCandidateResume(selectedRoleId, formData);
      setApplicantName("");
      setApplicantEmail("");
      setResumeFile(null);
      const input = document.getElementById("resume-upload") as HTMLInputElement | null;
      if (input) input.value = "";
      setNotice("Resume uploaded and text extracted. The original file was not retained.");
      await loadData(selectedRoleId);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Could not upload this resume.");
    } finally {
      setWorking(false);
    }
  };

  const handleEvaluate = async (applicationId: string) => {
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await api.evaluateCandidateApplication(applicationId);
      setSelectedApplicationId(applicationId);
      setNotice("Screening recommendation generated for recruiter review.");
      await loadData(selectedRoleId);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Candidate screening failed.");
    } finally {
      setWorking(false);
    }
  };

  const handleDeleteApplication = async (applicationId: string) => {
    if (!window.confirm("Delete this candidate application and its extracted resume text?")) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await api.deleteCandidateApplication(applicationId);
      if (selectedApplicationId === applicationId) setSelectedApplicationId("");
      setNotice("Candidate application and extracted resume text deleted.");
      await loadData(selectedRoleId);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Could not delete this application.");
    } finally {
      setWorking(false);
    }
  };

  const handleDraftInterview = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedApplicationId) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await api.draftCandidateInterviewEmail(selectedApplicationId, interviewDetails.trim());
      setNotice("Interview email draft saved. It has not been sent.");
      setInterviewDetails("");
      await loadData(selectedRoleId);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Could not create the interview draft.");
    } finally {
      setWorking(false);
    }
  };

  const handleCloseRole = async () => {
    if (!selectedRoleId) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await api.closeRecruitmentRole(selectedRoleId);
      setNotice("Job opening closed.");
      await loadData(selectedRoleId);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Could not close the job opening.");
    } finally {
      setWorking(false);
    }
  };

  const selectedRole = roles.find((role) => role.role_id === selectedRoleId);
  const selectedApplication = applications.find(
    (application) => application.application_id === selectedApplicationId,
  );

  return (
    <main className="space-y-6 pb-12">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-cream-300 pb-4">
        <div>
          <h1 className="text-2xl font-semibold text-cream-900">Recruitment &amp; Screening</h1>
          <p className="mt-1 max-w-3xl text-sm text-cream-700">
            Review job-related resume evidence and AI screening recommendations. Recruiters make all hiring decisions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadData(selectedRoleId)}
          disabled={loading || working}
          className="inline-flex items-center gap-2 rounded-md border border-cream-300 bg-cream-100 px-3 py-2 text-sm text-cream-800 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </header>

      {error && <p role="alert" className="rounded-md border border-terracotta-300 bg-terracotta-50 p-3 text-sm text-terracotta-800">{error}</p>}
      {notice && <p role="status" className="rounded-md border border-sage-300 bg-sage-50 p-3 text-sm text-sage-800">{notice}</p>}
      <p className="rounded-md border border-amberGold-500/30 bg-amberGold-50 p-3 text-sm text-amberGold-800">
        Screening is an assistive review aid, not an employment decision. Evidence is shown for recruiter verification; no applicant is automatically rejected or contacted.
      </p>
      <p className="text-xs text-cream-600">
        Screening sends extracted resume text to the configured AI provider after redacting email addresses and phone numbers. Use it only when your organization is authorized to process candidate data there.
      </p>

      <div className="grid gap-6 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.4fr)]">
        <div className="space-y-6">
          <section className="rounded-lg border border-cream-300 bg-cream-100 p-4">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-cream-900">
              <Plus className="h-4 w-4" /> Create job opening
            </h2>
            <form onSubmit={handleCreateRole} className="space-y-3">
              <label className="block text-xs font-medium text-cream-700">
                Job title
                <input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={2} maxLength={255}
                  className="mt-1 w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm text-cream-900" />
              </label>
              <label className="block text-xs font-medium text-cream-700">
                Description
                <textarea value={description} onChange={(event) => setDescription(event.target.value)} required minLength={10} maxLength={12000} rows={3}
                  className="mt-1 w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm text-cream-900" />
              </label>
              <label className="block text-xs font-medium text-cream-700">
                Job-related requirements
                <textarea value={requirements} onChange={(event) => setRequirements(event.target.value)} required minLength={3} maxLength={12000} rows={3}
                  className="mt-1 w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm text-cream-900" />
              </label>
              <button disabled={working} className="inline-flex items-center gap-2 rounded-md bg-sage-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
                <Plus className="h-4 w-4" /> Create opening
              </button>
            </form>
          </section>

          <section className="rounded-lg border border-cream-300 bg-cream-100 p-4">
            <div className="mb-4 flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-cream-900">
                <Briefcase className="h-4 w-4" /> Job openings
              </h2>
              <span className="text-xs text-cream-600">{roles.length} total</span>
            </div>
            {loading ? <p className="text-sm text-cream-700">Loading openings…</p> : roles.length === 0 ? (
              <p className="text-sm text-cream-700">Create a job opening to start reviewing applications.</p>
            ) : (
              <ul className="space-y-2">
                {roles.map((role) => (
                  <li key={role.role_id}>
                    <button type="button" onClick={() => {
                      setSelectedRoleId(role.role_id);
                      setSelectedApplicationId("");
                      void loadData(role.role_id);
                    }}
                      className={`w-full rounded-md border p-3 text-left ${role.role_id === selectedRoleId ? "border-sage-600 bg-sage-50" : "border-cream-300 bg-white hover:bg-cream-50"}`}>
                      <span className="flex items-center justify-between gap-2">
                        <span className="font-medium text-cream-900">{role.title}</span>
                        <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${role.status === "OPEN" ? "bg-sage-100 text-sage-800" : "bg-cream-200 text-cream-700"}`}>{role.status}</span>
                      </span>
                      <span className="mt-1 block line-clamp-2 text-xs text-cream-700">{role.description}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-6">
          <section className="rounded-lg border border-cream-300 bg-cream-100 p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="flex items-center gap-2 text-sm font-semibold text-cream-900">
                  <FileText className="h-4 w-4" /> Candidate applications
                </h2>
                {selectedRole && <p className="mt-1 text-xs text-cream-700">{selectedRole.title}</p>}
              </div>
              {selectedRole?.status === "OPEN" && (
                <button type="button" onClick={() => void handleCloseRole()} disabled={working}
                  className="rounded-md border border-cream-300 bg-white px-3 py-2 text-xs text-cream-800 disabled:opacity-50">
                  Close opening
                </button>
              )}
            </div>

            {selectedRole?.status === "OPEN" && (
              <form onSubmit={handleUploadResume} className="mb-5 grid gap-3 rounded-md border border-dashed border-cream-400 bg-white p-3 md:grid-cols-2">
                <label className="text-xs font-medium text-cream-700">
                  Resume (PDF or DOCX, max 10 MB)
                  <input id="resume-upload" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" required
                    onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)}
                    className="mt-1 block w-full text-xs text-cream-700 file:mr-2 file:rounded file:border-0 file:bg-cream-200 file:px-2 file:py-1 file:text-xs" />
                </label>
                <label className="text-xs font-medium text-cream-700">
                  Applicant name (optional)
                  <input value={applicantName} onChange={(event) => setApplicantName(event.target.value)} maxLength={128}
                    className="mt-1 w-full rounded-md border border-cream-300 px-3 py-2 text-sm" />
                </label>
                <label className="text-xs font-medium text-cream-700">
                  Applicant email (optional)
                  <input type="email" value={applicantEmail} onChange={(event) => setApplicantEmail(event.target.value)} maxLength={320}
                    className="mt-1 w-full rounded-md border border-cream-300 px-3 py-2 text-sm" />
                </label>
                <div className="flex items-end">
                  <button disabled={working || !resumeFile} className="rounded-md bg-cream-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
                    Upload resume
                  </button>
                </div>
              </form>
            )}

            {loading ? <p className="text-sm text-cream-700">Loading applications…</p> : !selectedRole ? (
              <p className="text-sm text-cream-700">Select a job opening to view candidates.</p>
            ) : applications.length === 0 ? (
              <p className="text-sm text-cream-700">No applications have been uploaded for this opening.</p>
            ) : (
              <ul className="space-y-2">
                {applications.map((application) => (
                  <li key={application.application_id} className={`rounded-md border p-3 ${application.application_id === selectedApplicationId ? "border-sage-600 bg-sage-50" : "border-cream-300 bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <button type="button" onClick={() => setSelectedApplicationId(application.application_id)} className="min-w-0 text-left">
                        <span className="flex items-center gap-2 font-medium text-cream-900">
                          <UserRound className="h-4 w-4 shrink-0" />
                          <span className="truncate">{application.applicant_name || application.resume_filename}</span>
                        </span>
                        <span className="mt-1 block text-xs text-cream-600">
                          {application.applicant_email || "No email provided"} · {application.status}
                          {application.screening_score !== null && ` · Score ${application.screening_score}/100`}
                        </span>
                      </button>
                      <button type="button" onClick={() => void handleEvaluate(application.application_id)} disabled={working}
                        className="inline-flex items-center gap-1 rounded-md border border-sage-700 px-2.5 py-1.5 text-xs font-medium text-sage-800 disabled:opacity-50">
                        <Sparkles className="h-3.5 w-3.5" /> {application.status === "EVALUATED" ? "Re-evaluate" : "Screen"}
                      </button>
                      <button type="button" onClick={() => void handleDeleteApplication(application.application_id)} disabled={working}
                        className="rounded-md border border-terracotta-300 px-2.5 py-1.5 text-xs text-terracotta-800 disabled:opacity-50">
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {selectedApplication && (
            <section className="space-y-4 rounded-lg border border-cream-300 bg-cream-100 p-4">
              <div>
                <h2 className="text-sm font-semibold text-cream-900">Recruiter review</h2>
                {selectedApplication.screening_summary ? (
                  <>
                    <div className="mt-3 flex items-center gap-3">
                      <span className="rounded-md bg-sage-100 px-3 py-1.5 text-sm font-semibold text-sage-800">
                        {selectedApplication.screening_score}/100
                      </span>
                      <p className="text-sm text-cream-800">{selectedApplication.screening_summary}</p>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div>
                        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-cream-700">Supported requirements</h3>
                        {selectedApplication.matched_requirements.length ? (
                          <ul className="list-disc space-y-1 pl-5 text-sm text-cream-800">
                            {selectedApplication.matched_requirements.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
                          </ul>
                        ) : <p className="text-sm text-cream-600">No matched requirements returned.</p>}
                      </div>
                      <div>
                        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-cream-700">Evidence quotes</h3>
                        {selectedApplication.evidence.length ? (
                          <ul className="space-y-3">
                            {selectedApplication.evidence.map((item, index) => (
                              <li key={`${item.requirement}-${index}`} className="rounded-md border border-cream-300 bg-white p-3 text-sm">
                                <p className="font-medium text-cream-900">{item.requirement}</p>
                                <blockquote className="my-1 border-l-2 border-sage-500 pl-2 text-cream-700">&ldquo;{item.quote}&rdquo;</blockquote>
                                <p className="text-xs text-cream-600">{item.assessment}</p>
                              </li>
                            ))}
                          </ul>
                        ) : <p className="text-sm text-cream-600">No evidence quotes returned.</p>}
                      </div>
                    </div>
                  </>
                ) : <p className="mt-2 text-sm text-cream-700">Run screening to generate a job-related recommendation and evidence for review.</p>}
              </div>

              <form onSubmit={handleDraftInterview} className="border-t border-cream-300 pt-4">
                <h3 className="mb-2 text-sm font-semibold text-cream-900">Draft an interview invitation</h3>
                <label className="block text-xs font-medium text-cream-700">
                  Interview details to include
                  <textarea value={interviewDetails} onChange={(event) => setInterviewDetails(event.target.value)} required minLength={3} maxLength={4000} rows={3}
                    placeholder="Proposed date, time, format, and any information the candidate needs"
                    className="mt-1 w-full rounded-md border border-cream-300 bg-white px-3 py-2 text-sm text-cream-900" />
                </label>
                <button disabled={working} className="mt-2 rounded-md border border-cream-400 bg-white px-3 py-2 text-sm text-cream-800 disabled:opacity-50">
                  Generate draft (does not send)
                </button>
                {selectedApplication.interview_email_subject && (
                  <div className="mt-3 rounded-md border border-cream-300 bg-white p-3">
                    <p className="text-xs font-semibold text-cream-800">{selectedApplication.interview_email_subject}</p>
                    <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-cream-700">{selectedApplication.interview_email_body}</pre>
                  </div>
                )}
              </form>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
