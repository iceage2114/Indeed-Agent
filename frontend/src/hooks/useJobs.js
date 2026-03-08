// useJobs.js — Fetches jobs from the FastAPI backend and exposes filtered results

import { useState, useEffect, useRef, useMemo } from "react";

export function useLocations() {
  const [locations, setLocations] = useState([]);

  useEffect(() => {
    fetch("/api/locations")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setLocations(Array.isArray(data) ? data : []))
      .catch(() => setLocations([]));
  }, []);

  return locations;
}

export function useJobs(refreshKey = 0) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isFirstLoad = useRef(true);

  useEffect(() => {
    // Only show the full-page spinner on the very first load.
    // Subsequent refreshes update silently so the page doesn't jump to the top.
    if (isFirstLoad.current) {
      setLoading(true);
    }
    fetch("/api/jobs")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setJobs(Array.isArray(data) ? data : []);
        setLoading(false);
        isFirstLoad.current = false;
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [refreshKey]);

  return { jobs, loading, error };
}

export function useAppliedJobs(refreshKey = 0) {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    fetch("/api/jobs/applied")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setJobs(Array.isArray(data) ? data : []))
      .catch(() => setJobs([]));
  }, [refreshKey]);

  return jobs;
}

export async function applyJob(id) {
  await fetch(`/api/jobs/${id}/apply`, { method: "POST" });
}

export async function unapplyJob(id) {
  await fetch(`/api/jobs/${id}/apply`, { method: "DELETE" });
}

export async function deleteJob(id) {
  await fetch(`/api/jobs/${id}`, { method: "DELETE" });
}

export async function wipeJobs() {
  await fetch("/api/jobs", { method: "DELETE" });
}

export function useFilteredJobs(jobs, { field, keyword, location }) {
  return useMemo(() => {
    let result = jobs;

    if (field && field !== "all") {
      result = result.filter((j) =>
        j.field?.toLowerCase().includes(field.toLowerCase())
      );
    }

    if (keyword.trim()) {
      const kw = keyword.toLowerCase();
      result = result.filter(
        (j) =>
          j.title?.toLowerCase().includes(kw) ||
          j.description?.toLowerCase().includes(kw)
      );
    }

    if (location.trim()) {
      const loc = location.toLowerCase();
      result = result.filter((j) =>
        j.location?.toLowerCase().includes(loc)
      );
    }

    return result;
  }, [jobs, field, keyword, location]);
}
