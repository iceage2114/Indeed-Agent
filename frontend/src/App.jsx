import { useState } from "react";
import Header from "./components/Header";
import FilterBar from "./components/FilterBar";
import JobList from "./components/JobList";
import AppliedPanel from "./components/AppliedPanel";
import ConfirmModal from "./components/ConfirmModal";
import TopMatchesPage from "./components/TopMatchesPage";
import { useJobs, useAppliedJobs, useFilteredJobs, applyJob, unapplyJob, deleteJob, wipeJobs } from "./hooks/useJobs";

export default function App() {
  const [view, setView] = useState("board"); // "board" | "matches"
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = () => setRefreshKey((k) => k + 1);

  const { jobs, loading, error } = useJobs(refreshKey);
  const appliedJobs = useAppliedJobs(refreshKey);

  const [filters, setFilters] = useState({
    field: "all",
    keyword: "",
    location: "",
  });

  const filteredJobs = useFilteredJobs(jobs, filters);

  // pending = { message, confirmLabel, confirmClass, action } | null
  const [pending, setPending] = useState(null);

  if (view === "matches") {
    return <TopMatchesPage onBack={() => setView("board")} />;
  }

  function handleFilterChange(key, value) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function handleApply(job) {
    setPending({
      message: `Mark "${job.title}" as applied?`,
      confirmLabel: "Mark Applied",
      confirmClass: "bg-green-600 hover:bg-green-700",
      action: async () => {
        await applyJob(job.id);
        refresh();
      },
    });
  }

  function handleDismiss(jobId) {
    const job = jobs.find((j) => j.id === jobId);
    setPending({
      message: `Remove "${job?.title ?? "this job"}" from your list?`,
      confirmLabel: "Remove",
      confirmClass: "bg-red-600 hover:bg-red-700",
      action: async () => {
        await deleteJob(jobId);
        refresh();
      },
    });
  }

  function handleWipe() {
    setPending({
      message: "Delete ALL jobs from the database? This cannot be undone.",
      confirmLabel: "Wipe DB",
      confirmClass: "bg-red-600 hover:bg-red-700",
      action: async () => {
        await wipeJobs();
        refresh();
      },
    });
  }

  function handleRemoveApplied(jobId) {
    const job = appliedJobs.find((j) => j.id === jobId);
    setPending({
      message: `Move "${job?.title ?? "this job"}" back to the job list?`,
      confirmLabel: "Move Back",
      confirmClass: "bg-blue-600 hover:bg-blue-700",
      action: async () => {
        await unapplyJob(jobId);
        refresh();
      },
    });
  }

  async function handleConfirm() {
    if (pending?.action) await pending.action();
    setPending(null);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header total={jobs.length} filtered={filteredJobs.length} onWipe={handleWipe} onViewMatches={() => setView("matches")} />
      <FilterBar
        field={filters.field}
        keyword={filters.keyword}
        location={filters.location}
        onChange={handleFilterChange}
      />
      <div className="max-w-screen-2xl mx-auto px-6 py-8 flex gap-6 items-start">
        <main className="flex-1 min-w-0">
          <JobList
            jobs={filteredJobs}
            loading={loading}
            error={error}
            onApply={handleApply}
            onDismiss={handleDismiss}
          />
        </main>
        <AppliedPanel jobs={appliedJobs} onRemove={handleRemoveApplied} />
      </div>
      <ConfirmModal
        message={pending?.message}
        confirmLabel={pending?.confirmLabel}
        confirmClass={pending?.confirmClass}
        onConfirm={handleConfirm}
        onCancel={() => setPending(null)}
      />
    </div>
  );
}
