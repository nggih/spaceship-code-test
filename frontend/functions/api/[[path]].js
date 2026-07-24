const DEFAULT_API_ORIGIN =
  "https://logistics-intelligence-api.nggih.workers.dev";

export async function onRequest(context) {
  const incoming = new URL(context.request.url);
  const upstream = new URL(
    `${incoming.pathname}${incoming.search}`,
    context.env.API_ORIGIN || DEFAULT_API_ORIGIN,
  );
  const headers = new Headers(context.request.headers);
  headers.delete("host");

  return fetch(
    new Request(upstream, {
      method: context.request.method,
      headers,
      body:
        context.request.method === "GET" || context.request.method === "HEAD"
          ? undefined
          : context.request.body,
      redirect: "manual",
    }),
  );
}
