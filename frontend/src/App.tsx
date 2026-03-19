import { useState, useEffect } from "react";
import CallInterface from "./components/CallInterface";
import ClaimProgress from "./components/ClaimProgress";
import { Shield, Loader2 } from "lucide-react";
import { getLatestClaim } from "./lib/api";

type AppState = "home" | "call" | "waiting" | "processing";

function App() {
  const [state, setState] = useState<AppState>("home");
  const [claimId, setClaimId] = useState<string | null>(null);

  const handleStartCall = () => {
    setState("call");
  };

  const handleCallEnd = () => {
    setState("waiting");
  };

  useEffect(() => {
    if (state !== "waiting") return;

    const pollForClaim = async () => {
      const claim = await getLatestClaim();
      if (claim && claim.id) {
        setClaimId(claim.id);
        setState("processing");
      }
    };

    pollForClaim();
    const interval = setInterval(pollForClaim, 2000);

    const timeout = setTimeout(() => {
      clearInterval(interval);
      if (state === "waiting") {
        setState("home");
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [state]);

  const handleReset = () => {
    setState("home");
    setClaimId(null);
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-neutral-200">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="p-2 border border-blue-600 bg-blue-50">
            <Shield className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h1 className="font-semibold text-lg text-neutral-900">
              SafeDrive Insurance
            </h1>
            <p className="text-sm text-neutral-500">Claims Center</p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-6 py-12">
        {state === "home" && (
          <div className="text-center max-w-2xl mx-auto">
            <div className="mb-8">
              <h2 className="text-4xl font-bold mb-4 text-neutral-900">
                File a Claim
              </h2>
              <p className="text-neutral-600 text-lg">
                Talk to our AI agent to quickly file your auto insurance claim.
                We'll guide you through the process and handle everything in the
                background.
              </p>
            </div>

            <button
              onClick={handleStartCall}
              className="inline-flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                />
              </svg>
              <span>Start Claim Call</span>
            </button>

            <div className="mt-12 grid grid-cols-3 gap-6 text-left">
              <div className="p-5 bg-neutral-50 border border-neutral-200">
                <div className="w-10 h-10 bg-blue-100 flex items-center justify-center mb-3">
                  <svg
                    className="w-5 h-5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
                <h3 className="font-medium mb-1 text-neutral-900">
                  Quick & Easy
                </h3>
                <p className="text-sm text-neutral-600">
                  File your claim in under 2 minutes with our AI assistant
                </p>
              </div>
              <div className="p-5 bg-neutral-50 border border-neutral-200">
                <div className="w-10 h-10 bg-blue-100 flex items-center justify-center mb-3">
                  <svg
                    className="w-5 h-5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                </div>
                <h3 className="font-medium mb-1 text-neutral-900">
                  Instant Processing
                </h3>
                <p className="text-sm text-neutral-600">
                  Watch your claim get processed in real-time
                </p>
              </div>
              <div className="p-5 bg-neutral-50 border border-neutral-200">
                <div className="w-10 h-10 bg-blue-100 flex items-center justify-center mb-3">
                  <svg
                    className="w-5 h-5 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                    />
                  </svg>
                </div>
                <h3 className="font-medium mb-1 text-neutral-900">Secure</h3>
                <p className="text-sm text-neutral-600">
                  Your information is protected and verified
                </p>
              </div>
            </div>

            {/* Demo Scenarios */}
            <div className="mt-12 p-6 bg-neutral-50 border border-neutral-200 text-left">
              <h3 className="text-lg font-semibold mb-4 text-neutral-900">
                Demo Scenarios
              </h3>
              <p className="text-sm text-neutral-600 mb-4">
                Use these phone numbers to see different customer scenarios:
              </p>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="p-3 bg-white border border-neutral-200">
                  <div className="flex justify-between">
                    <span className="font-mono text-emerald-600">555-0100</span>
                    <span className="font-mono text-neutral-400">94102</span>
                  </div>
                  <div className="text-neutral-900">Sarah Johnson</div>
                  <div className="text-neutral-400 text-xs">
                    2022 Silver Toyota Camry
                  </div>
                  <div className="text-neutral-500 text-xs">
                    Gold member, clean history → Fast approval
                  </div>
                </div>
                <div className="p-3 bg-white border border-neutral-200">
                  <div className="flex justify-between">
                    <span className="font-mono text-amber-600">555-0200</span>
                    <span className="font-mono text-neutral-400">90210</span>
                  </div>
                  <div className="text-neutral-900">Mike Thompson</div>
                  <div className="text-neutral-400 text-xs">
                    2019 Black Ford F-150
                  </div>
                  <div className="text-neutral-500 text-xs">
                    4 prior claims → Extended review, fraud check
                  </div>
                </div>
                <div className="p-3 bg-white border border-neutral-200">
                  <div className="flex justify-between">
                    <span className="font-mono text-violet-600">555-0300</span>
                    <span className="font-mono text-neutral-400">10001</span>
                  </div>
                  <div className="text-neutral-900">Emma Rodriguez</div>
                  <div className="text-neutral-400 text-xs">
                    2024 Blue BMW X5
                  </div>
                  <div className="text-neutral-500 text-xs">
                    Platinum VIP → Priority service, concierge shop
                  </div>
                </div>
                <div className="p-3 bg-white border border-neutral-200">
                  <div className="flex justify-between">
                    <span className="font-mono text-red-600">555-0400</span>
                    <span className="font-mono text-neutral-400">33101</span>
                  </div>
                  <div className="text-neutral-900">James Wilson</div>
                  <div className="text-neutral-400 text-xs">
                    2020 White Honda Civic
                  </div>
                  <div className="text-neutral-500 text-xs">
                    Payment overdue → Account warning
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {state === "call" && <CallInterface onCallEnd={handleCallEnd} />}

        {state === "waiting" && (
          <div className="max-w-md mx-auto text-center">
            <div className="p-8 bg-neutral-50 border border-neutral-200">
              <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
              </div>
              <h2 className="text-xl font-semibold mb-2 text-neutral-900">
                Processing Your Call
              </h2>
              <p className="text-neutral-600">
                Please wait while we finalize your claim submission...
              </p>
            </div>
          </div>
        )}

        {state === "processing" && claimId && (
          <ClaimProgress claimId={claimId} onReset={handleReset} />
        )}
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 border-t border-neutral-200 bg-white">
        <div className="max-w-5xl mx-auto px-6 py-3 text-center text-sm text-neutral-500">
          Demo powered by{" "}
          <span className="text-blue-600">Render Workflows</span> +{" "}
          <span className="text-blue-600">LiveKit</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
