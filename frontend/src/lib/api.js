import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});


export async function startScan(payload) {
  const { data } = await client.post("/api/scan", payload);
  return data;
}


export async function getScanStatus(scanId) {
  const { data } = await client.get(`/api/scan/${scanId}/status`);
  return data;
}


export async function getScanReport(scanId) {
  const { data } = await client.get(`/api/scan/${scanId}/report`);
  return data;
}