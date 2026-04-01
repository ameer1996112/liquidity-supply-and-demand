/**
 * Server-side proxy for trading mode changes.
 *
 * NEXT_PUBLIC_* env vars are baked into the JS bundle at build time, so
 * they can't reliably carry secrets set after deployment. This route runs
 * on the server where ADMIN_API_KEY is available at runtime, keeping the
 * key out of the browser entirely.
 */
import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const ADMIN_KEY = process.env.ADMIN_API_KEY || process.env.NEXT_PUBLIC_ADMIN_API_KEY || '';

export async function GET() {
  const res = await fetch(`${BACKEND_URL}/api/v1/config/trading-mode`, {
    headers: {
      'Content-Type': 'application/json',
      ...(ADMIN_KEY ? { 'X-Admin-API-Key': ADMIN_KEY } : {}),
    },
    cache: 'no-store',
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  const res = await fetch(`${BACKEND_URL}/api/v1/config/trading-mode`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(ADMIN_KEY ? { 'X-Admin-API-Key': ADMIN_KEY } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
