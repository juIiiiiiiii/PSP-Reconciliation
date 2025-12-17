/**
 * Supabase Edge Function: Webhook Handler
 * Handles PSP webhooks at the edge for low latency
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Get Supabase client
    const supabaseUrl = Deno.env.get('SUPABASE_URL')!
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const supabase = createClient(supabaseUrl, supabaseKey)

    // Extract tenant and PSP from path
    const url = new URL(req.url)
    const pathParts = url.pathname.split('/')
    const tenantId = pathParts[2]
    const pspConnectionId = pathParts[3]

    if (!tenantId || !pspConnectionId) {
      return new Response(
        JSON.stringify({ error: 'Missing tenant_id or psp_connection_id' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Get webhook body
    const body = await req.text()
    const webhookData = JSON.parse(body)

    // Validate webhook signature (implementation depends on PSP)
    // TODO: Implement signature validation

    // Generate idempotency key
    const idempotencyKey = `${pspConnectionId}:${webhookData.id || webhookData.event_id}:${webhookData.type || 'unknown'}:${Date.now()}`

    // Check idempotency (using Supabase KV or database)
    const { data: existing } = await supabase
      .from('raw_event_metadata')
      .select('raw_event_id')
      .eq('tenant_id', tenantId)
      .eq('idempotency_key', idempotencyKey)
      .single()

    if (existing) {
      // Already processed
      return new Response(
        JSON.stringify({ status: 'duplicate', idempotency_key: idempotencyKey }),
        { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Store raw event in R2 (via Cloudflare) or Supabase Storage
    // TODO: Implement storage

    // Publish to Kinesis or Supabase Realtime
    // TODO: Implement event publishing

    return new Response(
      JSON.stringify({ status: 'processed', idempotency_key: idempotencyKey }),
      { status: 200, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  }
})


