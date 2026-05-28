async function getBackendStatus() {
  try {
    const res = await fetch("http://127.0.0.1:8000/admin/", {
      cache: "no-store",
    });

    return res.status;
  } catch (error) {
    return "Backend Offline";
  }
}

export default async function Home() {
  const status = await getBackendStatus();

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-24">
      <h1 className="text-5xl font-bold mb-6">
        Rasti SaaS Platform
      </h1>

      <p className="text-xl mb-4">
        Frontend Connected
      </p>

      <div className="p-4 rounded bg-gray-100">
        Backend Status: {String(status)}
      </div>
    </main>
  );
}