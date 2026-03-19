import { useState, useEffect } from 'react';
import { getClaim } from '../lib/api';
import { 
  CheckCircle2, 
  Circle, 
  Loader2, 
  FileText, 
  Shield, 
  Search, 
  Calculator, 
  MapPin, 
  Mail,
  ArrowRight,
  Star
} from 'lucide-react';

interface ClaimProgressProps {
  claimId: string;
  onReset: () => void;
}

const STEPS = [
  { id: 'verify_policy', name: 'Verifying Policy', icon: Shield, description: 'Looking up your insurance policy' },
  { id: 'analyze_damage', name: 'Analyzing Damage', icon: Search, description: 'AI analyzing damage description' },
  { id: 'fraud_check', name: 'Security Check', icon: FileText, description: 'Running verification checks' },
  { id: 'generate_estimate', name: 'Generating Estimate', icon: Calculator, description: 'Calculating repair costs' },
  { id: 'find_shops', name: 'Finding Repair Shops', icon: MapPin, description: 'Locating nearby approved shops' },
  { id: 'send_notification', name: 'Sending Confirmation', icon: Mail, description: 'Sending email and SMS' },
];

export default function ClaimProgress({ claimId, onReset }: ClaimProgressProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    const fetchClaim = async () => {
      try {
        const data = await getClaim(claimId);
        
        if (data.status === 'completed') {
          setIsComplete(true);
          setCurrentStepIndex(STEPS.length);
        } else {
          const stepIndex = STEPS.findIndex(s => s.id === data.workflow_status.current_step);
          if (stepIndex >= 0) {
            setCurrentStepIndex(stepIndex);
          }
        }
      } catch (err) {
        console.error('Failed to fetch claim:', err);
      }
    };

    fetchClaim();
    const interval = setInterval(fetchClaim, 2000);

    return () => {
      clearInterval(interval);
    };
  }, [claimId]);

  const getStepStatus = (index: number) => {
    if (isComplete || index < currentStepIndex) return 'completed';
    if (index === currentStepIndex && !isComplete) return 'running';
    return 'pending';
  };

  return (
    <div className="max-w-3xl mx-auto">
      {/* Claim ID Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 text-sm font-medium mb-4">
          <FileText className="w-4 h-4" />
          Claim #{claimId}
        </div>
        <h2 className="text-3xl font-bold mb-2 text-neutral-900">
          {isComplete ? 'Claim Approved!' : 'Processing Your Claim'}
        </h2>
        <p className="text-neutral-500">
          {isComplete 
            ? 'Your claim has been processed successfully.' 
            : 'Please wait while we process your claim in the background.'}
        </p>
      </div>

      {/* Progress Steps */}
      <div className="bg-neutral-50 border border-neutral-200 p-6 mb-6">
        <div className="space-y-1">
          {STEPS.map((step, index) => {
            const status = getStepStatus(index);
            const Icon = step.icon;
            
            return (
              <div key={step.id} className="relative">
                {/* Connector line */}
                {index < STEPS.length - 1 && (
                  <div 
                    className={`absolute left-5 top-12 w-0.5 h-8 -translate-x-1/2 transition-colors duration-500 ${
                      status === 'completed' ? 'bg-emerald-500' : 'bg-neutral-300'
                    }`}
                  />
                )}
                
                <div className={`flex items-center gap-4 p-3 transition-colors ${
                  status === 'running' ? 'bg-blue-50' : ''
                }`}>
                  {/* Status Icon */}
                  <div className={`w-10 h-10 flex items-center justify-center transition-colors ${
                    status === 'completed' 
                      ? 'bg-emerald-100 text-emerald-600' 
                      : status === 'running'
                        ? 'bg-blue-100 text-blue-600'
                        : 'bg-neutral-200 text-neutral-400'
                  }`}>
                    {status === 'completed' ? (
                      <CheckCircle2 className="w-5 h-5" />
                    ) : status === 'running' ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Circle className="w-5 h-5" />
                    )}
                  </div>
                  
                  {/* Step Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Icon className={`w-4 h-4 ${
                        status === 'completed' 
                          ? 'text-emerald-600' 
                          : status === 'running'
                            ? 'text-blue-600'
                            : 'text-neutral-400'
                      }`} />
                      <span className={`font-medium ${
                        status === 'pending' ? 'text-neutral-400' : 'text-neutral-900'
                      }`}>
                        {step.name}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-500 mt-0.5">{step.description}</p>
                  </div>
                  
                  {/* Status Badge */}
                  {status === 'running' && (
                    <span className="text-xs text-blue-600 font-medium">Processing...</span>
                  )}
                  {status === 'completed' && (
                    <span className="text-xs text-emerald-600 font-medium">Done</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Results Card (shown when complete) */}
      {isComplete && (
        <div className="bg-neutral-50 border border-neutral-200 p-6 space-y-6">
          <h3 className="text-xl font-semibold flex items-center gap-2 text-neutral-900">
            <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            Claim Summary
          </h3>
          
          {/* Estimate */}
          <div className="p-4 bg-emerald-50 border border-emerald-200">
            <div className="text-sm text-emerald-700 mb-1">Repair Estimate</div>
            <div className="text-3xl font-bold text-neutral-900">$2,347.00</div>
            <div className="text-sm text-neutral-600 mt-1">
              Your deductible: $500.00 • Insurance covers: $1,847.00
            </div>
          </div>
          
          {/* Damage Assessment */}
          <div>
            <div className="text-sm text-neutral-500 mb-2">Damage Assessment</div>
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1 bg-white border border-neutral-200 text-sm text-neutral-900">Rear Bumper</span>
              <span className="px-3 py-1 bg-white border border-neutral-200 text-sm text-neutral-900">Trunk</span>
              <span className="px-3 py-1 bg-white border border-neutral-200 text-sm text-neutral-900">Tail Light</span>
            </div>
            <div className="mt-2 text-sm">
              <span className="text-amber-600">Moderate</span>
              <span className="text-neutral-500"> severity • 87% confidence</span>
            </div>
          </div>
          
          {/* Repair Shops */}
          <div>
            <div className="text-sm text-neutral-500 mb-3">Recommended Repair Shops</div>
            <div className="space-y-2">
              {[
                { name: 'AutoFix Pro', distance: '1.2 mi', rating: 4.8, wait: 3 },
                { name: 'CarCare Center', distance: '2.5 mi', rating: 4.6, wait: 2 },
                { name: 'Bay Auto Body', distance: '3.1 mi', rating: 4.9, wait: 5 },
              ].map((shop) => (
                <div 
                  key={shop.name}
                  className="flex items-center justify-between p-3 bg-white border border-neutral-200"
                >
                  <div>
                    <div className="font-medium text-neutral-900">{shop.name}</div>
                    <div className="text-sm text-neutral-500">{shop.distance} away • {shop.wait} day wait</div>
                  </div>
                  <div className="flex items-center gap-1 text-amber-500">
                    <Star className="w-4 h-4 fill-current" />
                    <span className="text-sm font-medium">{shop.rating}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* Next Steps */}
          <div className="pt-4 border-t border-neutral-200">
            <div className="text-sm text-neutral-500 mb-3">Next Steps</div>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2 text-neutral-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Confirmation email sent to your registered address</span>
              </li>
              <li className="flex items-center gap-2 text-neutral-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>SMS notification sent to your phone</span>
              </li>
              <li className="flex items-center gap-2 text-neutral-900">
                <ArrowRight className="w-4 h-4 text-blue-600" />
                <span>Schedule a repair appointment with any recommended shop</span>
              </li>
            </ul>
          </div>
          
          {/* Action Button */}
          <button
            onClick={onReset}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors"
          >
            Start New Claim
          </button>
        </div>
      )}
    </div>
  );
}
