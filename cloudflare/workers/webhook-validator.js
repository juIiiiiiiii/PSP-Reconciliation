/**
 * Cloudflare Worker: Webhook Validator
 * Validates PSP webhook signatures at the edge
 */

export default {
  async fetch(request, env) {
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Webhook-Signature',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // Extract tenant and PSP from path
      const url = new URL(request.url);
      const pathParts = url.pathname.split('/');
      const tenantId = pathParts[2];
      const pspConnectionId = pathParts[3];

      if (!tenantId || !pspConnectionId) {
        return new Response(
          JSON.stringify({ error: 'Missing tenant_id or psp_connection_id' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Get webhook body
      const body = await request.text();
      const signature = request.headers.get('X-Webhook-Signature');

      // Get webhook secret from KV
      const secretKey = `webhook_secret:${tenantId}:${pspConnectionId}`;
      const secret = await env.WEBHOOK_SECRETS.get(secretKey);

      if (!secret) {
        return new Response(
          JSON.stringify({ error: 'Webhook secret not found' }),
          { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Validate signature (HMAC-SHA256)
      const crypto = globalThis.crypto;
      const encoder = new TextEncoder();
      const key = await crypto.subtle.importKey(
        'raw',
        encoder.encode(secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['sign']
      );

      const signatureBuffer = await crypto.subtle.sign('HMAC', key, encoder.encode(body));
      const computedSignature = Array.from(new Uint8Array(signatureBuffer))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');

      if (signature !== computedSignature) {
        return new Response(
          JSON.stringify({ error: 'Invalid signature' }),
          { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      // Check idempotency in KV
      const idempotencyKey = request.headers.get('X-Idempotency-Key');
      if (idempotencyKey) {
        const idempotencyKeyFull = `idempotency:${tenantId}:${pspConnectionId}:${idempotencyKey}`;
        const existing = await env.IDEMPOTENCY_KV.get(idempotencyKeyFull);
        
        if (existing) {
          return new Response(
            JSON.stringify({ status: 'duplicate', idempotency_key: idempotencyKey }),
            { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
          );
        }

        // Store idempotency key (TTL: 7 days)
        await env.IDEMPOTENCY_KV.put(idempotencyKeyFull, 'processed', { expirationTtl: 604800 });
      }

      // Forward to backend API
      const backendUrl = env.BACKEND_API_URL || 'https://api.psp-reconciliation.com';
      const response = await fetch(`${backendUrl}/webhooks/${tenantId}/${pspConnectionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Validated': 'true',
        },
        body: body,
      });

      return new Response(await response.text(), {
        status: response.status,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });

    } catch (error) {
      return new Response(
        JSON.stringify({ error: error.message }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }
  },
};


