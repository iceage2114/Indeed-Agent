// FilterBar.jsx � Field, keyword, and location filters
import { useLocations } from "../hooks/useJobs";
const FIELD_OPTIONS = [
  { value: "all", label: "All Fields" },
  { value: "entry level software engineering", label: "Software Engineering" },
  { value: "entry level cybersecurity", label: "Cybersecurity" },
  { value: "IT technician", label: "IT Technician" },
];

export default function FilterBar({ field, keyword, location, onChange }) {
  const locations = useLocations();
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10 shadow-sm">
      <div className="max-w-7xl mx-auto flex flex-wrap gap-4 items-center">
        {/* Field dropdown */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Field
          </label>
          <select
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={field}
            onChange={(e) => onChange("field", e.target.value)}
          >
            {FIELD_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Keyword search */}
        <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Keyword
          </label>
          <input
            type="text"
            placeholder="Search title or description..."
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={keyword}
            onChange={(e) => onChange("keyword", e.target.value)}
          />
        </div>

        {/* Location dropdown */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            Location
          </label>
          <select
            className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={location}
            onChange={(e) => onChange("location", e.target.value)}
          >
            <option value="">All Locations</option>
            {locations.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>
        </div>

        {/* Reset */}
        {(field !== "all" || keyword || location) && (
          <button
            className="mt-5 text-sm text-blue-600 hover:underline"
            onClick={() => {
              onChange("field", "all");
              onChange("keyword", "");
              onChange("location", "");
            }}
          >
            Clear filters
          </button>
        )}
      </div>
    </div>
  );
}
