// JobList.jsx – Renders list of JobCard components

import JobCard from "./JobCard";

export default function JobList({ jobs, loading, error, onApply, onDismiss }) {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-12 text-center">
        <p className="text-red-600 font-semibold">Failed to load jobs: {error}</p>
        <p className="text-sm text-gray-500 mt-2">
          Make sure the backend API is running on port 8000.
        </p>
      </div>
    );
  }

  if (!jobs.length) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-16 text-center">
        <p className="text-gray-400 text-lg">No jobs match your filters.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {jobs.map((job) => (
        <JobCard key={job.id} job={job} onApply={onApply} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
