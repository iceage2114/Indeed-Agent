// AppliedPanel.jsx - Sidebar tracking jobs the user has marked as applied

function formatAppliedAt(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return null;
  }
}

export default function AppliedPanel({ jobs, onRemove }) {
  return (
    <aside className="w-72 flex-shrink-0 bg-white rounded-xl shadow-sm border border-gray-200 p-5 sticky top-6 self-start">
      <h2 className="text-base font-semibold text-gray-800 mb-1">
        Applied Jobs
      </h2>
      <p className="text-xs text-gray-400 mb-4">
        {jobs.length} application{jobs.length !== 1 ? "s" : ""} tracked
      </p>

      {jobs.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-8 leading-relaxed">
          No applications yet.
          <br />
          Hit the green &#10003; on any job to track it here.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {jobs.map((job) => (
            <li
              key={job.id}
              className="flex items-start justify-between gap-2 border-b border-gray-100 pb-3 last:border-0 last:pb-0"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 leading-snug truncate">
                  {job.title}
                </p>
                <p className="text-xs text-gray-500 truncate">{job.company}</p>
                {job.applied_at && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Applied {formatAppliedAt(job.applied_at)}
                  </p>
                )}
              </div>
              <button
                onClick={() => onRemove(job.id)}
                title="Move back to job list"
                className="flex-shrink-0 text-gray-300 hover:text-red-500 transition-colors text-base leading-none mt-0.5"
              >
                &#x2715;
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
