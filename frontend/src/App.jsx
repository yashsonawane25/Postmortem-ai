import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Activity, ShieldAlert, Cpu, Database, 
  Terminal, FileWarning, RefreshCw, ServerCrash,
  DollarSign, TrendingDown, LogOut, Code, Copy, CheckCircle2
} from 'lucide-react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer 
} from 'recharts';
import { Show, SignInButton, SignUpButton, UserButton, useAuth, useUser } from '@clerk/react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [metrics, setMetrics] = useState({ cpu_cores: 0, memory_mib: 0 });
  const [logs, setLogs] = useState([]);
  const [aiReport, setAiReport] = useState(null);
  const [chaosStatus, setChaosStatus] = useState([]);
  const [resilience, setResilience] = useState({ total_experiments: 0, failed_experiments: 0, resilience_score: 100 });
  const [chartData, setChartData] = useState([]);
  const [costInsights, setCostInsights] = useState([]);
  const [clusterStatus, setClusterStatus] = useState({ connected: false, last_seen: null });
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [apiError, setApiError] = useState(null);

  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { user } = useUser();

  const fetchData = async () => {
    if (!isSignedIn) return;
    try {
      const token = await getToken();
      const config = { headers: { Authorization: `Bearer ${token}` } };
      
      const [resMetrics, resLogs, resReport, resChaos, resResilience, resCost, resCluster] = await Promise.all([
        axios.get(`${API_BASE}/metrics`, config).catch(() => ({ data: { cpu_cores: 0, memory_mib: 0 } })),
        axios.get(`${API_BASE}/logs`, config).catch(() => ({ data: { logs: [] } })),
        axios.get(`${API_BASE}/ai-report`, config).catch(() => ({ data: null })),
        axios.get(`${API_BASE}/chaos-status`, config).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}/resilience-score`, config).catch(() => ({ data: { total_experiments: 0, failed_experiments: 0, resilience_score: 100 } })),
        axios.get(`${API_BASE}/cost-insights`, config).catch(() => ({ data: [] })),
        axios.get(`${API_BASE}/cluster-status`, config).catch(() => ({ data: { connected: false, last_seen: null } }))
      ]);

      setClusterStatus(resCluster.data);

      setMetrics(resMetrics.data);
      setLogs(resLogs.data.logs || []);
      
      if (resReport.data && resReport.data.status !== 'no_reports') {
        setAiReport(resReport.data);
      }
      
      setChaosStatus(resChaos.data || []);
      setResilience(resResilience.data || { total_experiments: 0, failed_experiments: 0, resilience_score: 100 });
      setCostInsights(resCost.data || []);

      // Update Chart
      const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: 'numeric', minute: 'numeric', second: 'numeric' });
      setChartData(prev => {
        const newData = [...prev, { time, cpu: parseFloat(resMetrics.data.cpu_cores || 0).toFixed(2), memory: parseFloat(resMetrics.data.memory_mib || 0).toFixed(0) }];
        return newData.slice(-15); // keep last 15 points
      });

    } catch (err) {
      console.error("Error fetching data", err);
    }
  };

  useEffect(() => {
    if (isSignedIn) {
      fetchData();
      const interval = setInterval(fetchData, 5000);
      return () => clearInterval(interval);
    }
  }, [isSignedIn, getToken]);

  const triggerChaos = async () => {
    try {
      // In a real scenario, this would call the backend to execute the bash script.
      // Since our script runs externally, we just provide instructions or call an endpoint if we added one.
      alert('Run ./chaos/random-pod-kill.sh in your terminal to trigger chaos!');
    } catch (err) {
      console.error(err);
    }
  };

  const generateApiKey = async () => {
    try {
      setApiError(null);
      const token = await getToken();
      const config = { headers: { Authorization: `Bearer ${token}` } };
      const res = await axios.post(`${API_BASE}/api/keys`, {}, config);
      setApiKey(res.data.api_key);
    } catch (err) {
      console.error("Failed to generate API key", err);
      setApiError(err.message || "Failed to generate API key. Is the backend running?");
    }
  };

  const copyCommand = () => {
    const cmd = `helm repo add sre-agent https://your-repo.github.io/charts\nhelm install sre-agent sre-agent/sre-agent \\\n  --set apiKey=${apiKey || "YOUR_API_KEY"} \\\n  --set backendUrl=${API_BASE}`;
    navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      <Show when="signed-out">
        <div className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden bg-[#050505]">
          {/* Animated Background Gradients & Grid */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary-600/10 rounded-full blur-[120px] pointer-events-none"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[100px] pointer-events-none"></div>
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px]"></div>

          <div className="relative z-10 flex flex-col items-center max-w-3xl text-center px-4">
            <div className="mb-8 inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-dark-800/80 border border-dark-600/50 backdrop-blur-md shadow-lg">
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success-500"></span>
              </span>
              <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">System Online</span>
            </div>

            <div className="bg-primary-500/10 p-5 rounded-2xl mb-8 border border-primary-500/20 backdrop-blur-xl shadow-[0_0_30px_rgba(59,130,246,0.15)]">
              <Activity size={56} className="text-primary-400" />
            </div>
            
            <h1 className="text-5xl md:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-gray-200 to-gray-500 mb-6 tracking-tight drop-shadow-sm">
              PostmortemAI
            </h1>
            
            <p className="text-lg md:text-xl text-gray-400 mb-12 max-w-2xl leading-relaxed">
              The autonomous SRE platform that detects incidents, injects chaos, tracks FinOps, and leverages AI to write your postmortems.
            </p>

            <div className="flex flex-col sm:flex-row gap-5 w-full justify-center">
              <SignInButton mode="modal">
                <button className="group relative flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-500 text-white px-8 py-3.5 rounded-xl font-bold transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)] overflow-hidden border border-primary-500/50">
                  <div className="absolute inset-0 bg-white/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out"></div>
                  <span className="relative flex items-center gap-2">
                    Access Dashboard
                  </span>
                </button>
              </SignInButton>
              
              <SignUpButton mode="modal">
                <button className="flex items-center justify-center gap-2 bg-dark-800/80 hover:bg-dark-700 text-white px-8 py-3.5 rounded-xl font-bold transition-all border border-dark-600/80 backdrop-blur-sm shadow-lg hover:border-gray-500/50">
                  Create Account
                </button>
              </SignUpButton>
            </div>
          </div>
        </div>
      </Show>
      <Show when="signed-in">
        <div className="min-h-screen p-6 flex flex-col gap-6">
      {/* Header */}
      <header className="flex justify-between items-center pb-2 border-b border-dark-600/50">
        <div className="flex items-center gap-3">
          <div className="bg-primary-500/20 p-2 rounded-lg text-primary-400">
            <Activity size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">PostmortemAI</h1>
            <p className="text-sm text-gray-400">Autonomous SRE Platform & ChaosGuard</p>
          </div>
        </div>
        <div className="flex flex-col items-center">
           <div className="text-xs text-gray-400 uppercase tracking-widest font-bold mb-1">Tenant ID</div>
           <div className="bg-dark-600/50 px-3 py-1 rounded-md text-sm text-primary-400 font-mono border border-primary-500/20">
             {user?.id?.substring(0, 12)}...
           </div>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={triggerChaos}
            className="flex items-center gap-2 bg-danger-500/10 hover:bg-danger-500/20 text-danger-400 px-4 py-2 rounded-lg transition-colors border border-danger-500/20 font-medium"
          >
            <ServerCrash size={18} />
            Trigger Chaos
          </button>
          <div className="border-l border-dark-600/50 pl-4 flex items-center gap-3">
            <div className="text-right hidden sm:block">
               <div className="text-sm font-medium text-white">{user?.primaryEmailAddress?.emailAddress}</div>
            </div>
            <UserButton afterSignOutUrl="/" appearance={{ elements: { userButtonAvatarBox: "w-10 h-10 border border-dark-600" } }} />
          </div>
        </div>
      </header>

      {!clusterStatus.connected ? (
        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="max-w-2xl w-full glass-panel p-8 md:p-12 border-primary-500/30 shadow-[0_0_50px_rgba(59,130,246,0.1)] relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary-500 to-purple-500"></div>
            
            <div className="flex flex-col items-center text-center mb-8">
              <div className="bg-dark-600/50 p-4 rounded-full mb-6 border border-dark-400">
                <Database size={48} className="text-primary-400" />
              </div>
              <h2 className="text-3xl font-bold text-white mb-4">Connect Your Cluster</h2>
              <p className="text-gray-400 leading-relaxed max-w-lg">
                Your SaaS foundation is ready. To begin monitoring and analyzing incidents, install the lightweight PostmortemAI agent in your Kubernetes cluster.
              </p>
            </div>

            {!apiKey ? (
              <div className="flex flex-col items-center gap-4">
                <button 
                  onClick={generateApiKey}
                  className="bg-primary-600 hover:bg-primary-500 text-white px-8 py-3 rounded-xl font-medium transition-colors shadow-lg shadow-primary-500/20 flex items-center gap-2"
                >
                  <Code size={20} />
                  Generate API Key & Instructions
                </button>
                {apiError && (
                  <div className="text-danger-400 text-sm bg-danger-500/10 px-4 py-2 rounded-lg border border-danger-500/20">
                    {apiError}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="bg-dark-900 rounded-lg border border-dark-600 p-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Helm Installation Command</span>
                    <button 
                      onClick={copyCommand}
                      className="text-gray-400 hover:text-white transition-colors p-1"
                      title="Copy to clipboard"
                    >
                      {copied ? <CheckCircle2 size={18} className="text-success-400" /> : <Copy size={18} />}
                    </button>
                  </div>
                  <pre className="text-sm font-mono text-primary-400 overflow-x-auto whitespace-pre-wrap leading-relaxed">
{`helm repo add sre-agent https://your-repo.github.io/charts
helm install sre-agent sre-agent/sre-agent \\
  --set apiKey=${apiKey} \\
  --set backendUrl=${API_BASE}`}
                  </pre>
                </div>
                
                <div className="flex items-center justify-center gap-3 text-sm text-gray-400 bg-dark-800/50 p-4 rounded-lg border border-dark-600/50">
                  <RefreshCw size={16} className="animate-spin text-primary-500" />
                  Waiting for agent heartbeat...
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <>
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="stat-card">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-gray-400 font-medium">Resilience Score</h3>
            <ShieldAlert size={20} className={resilience.resilience_score > 80 ? 'text-success-400' : 'text-danger-400'} />
          </div>
          <p className="text-4xl font-bold text-white">
            {parseFloat(resilience.resilience_score).toFixed(0)}%
          </p>
          <div className="absolute -bottom-6 -right-6 text-dark-600/30">
            <ShieldAlert size={100} />
          </div>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-gray-400 font-medium">Total Experiments</h3>
            <Activity size={20} className="text-primary-400" />
          </div>
          <p className="text-4xl font-bold text-white">{resilience.total_experiments}</p>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-gray-400 font-medium">Failed Experiments</h3>
            <ServerCrash size={20} className="text-danger-400" />
          </div>
          <p className="text-4xl font-bold text-white">{resilience.failed_experiments}</p>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-gray-400 font-medium">System CPU</h3>
            <Cpu size={20} className="text-primary-400" />
          </div>
          <p className="text-4xl font-bold text-white">
            {parseFloat(metrics.cpu_cores).toFixed(2)} <span className="text-xl text-gray-500 font-normal">cores</span>
          </p>
        </div>

        <div className="stat-card">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-gray-400 font-medium">Cluster Cost</h3>
            <DollarSign size={20} className="text-green-400" />
          </div>
          <p className="text-4xl font-bold text-white">
            ${costInsights.reduce((sum, item) => sum + item.total_cost, 0).toFixed(2)}
          </p>
          <div className="absolute -bottom-6 -right-6 text-dark-600/30">
            <DollarSign size={100} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Left Column */}
        <div className="flex flex-col gap-6 col-span-1 lg:col-span-2">
          
          {/* AI Insights Panel */}
          <div className="glass-panel flex flex-col overflow-hidden border-primary-500/30 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
            <div className="bg-primary-500/10 px-6 py-4 flex items-center justify-between border-b border-primary-500/20">
              <div className="flex items-center gap-2 text-primary-400 font-semibold">
                <ShieldAlert size={20} />
                AI Incident Insights
              </div>
              {aiReport && (
                <div className="text-xs bg-dark-900 px-3 py-1 rounded-full text-gray-300 border border-dark-600">
                  {aiReport.created_at.split('T')[1].split('.')[0]}
                </div>
              )}
            </div>
            <div className="p-6">
              {aiReport ? (
                <div className="space-y-6">
                  <div className="flex gap-4 items-start">
                    <div className="bg-danger-500/10 p-3 rounded-lg text-danger-400 border border-danger-500/20">
                      <FileWarning size={24} />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-white mb-1">
                        {aiReport.alert_name} <span className="text-sm font-normal text-gray-400 ml-2">Confidence: {aiReport.report_data.confidence_pct}%</span>
                      </h3>
                      <p className="text-gray-300 leading-relaxed text-sm">
                        <span className="text-gray-400 font-medium">Root Cause:</span> {aiReport.report_data.root_cause}
                      </p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-dark-900 p-4 rounded-lg border border-dark-600">
                      <h4 className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-2">Impact</h4>
                      <p className="text-gray-200 text-sm">{aiReport.report_data.impact}</p>
                    </div>
                    <div className="bg-dark-900 p-4 rounded-lg border border-dark-600">
                      <h4 className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-2">Recommended Fix</h4>
                      <p className="text-gray-200 text-sm">{aiReport.report_data.recommended_fix}</p>
                    </div>
                  </div>
                  
                  {aiReport.report_data.kubernetes_fix_yaml && (
                    <div className="bg-dark-900 p-4 rounded-lg border border-dark-600 overflow-x-auto">
                      <h4 className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-2">Kubernetes Fix YAML</h4>
                      <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">{aiReport.report_data.kubernetes_fix_yaml}</pre>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                  <ShieldAlert size={48} className="mb-4 opacity-50" />
                  <p>No recent incidents detected. System is healthy.</p>
                </div>
              )}
            </div>
          </div>

          {/* System Health Chart */}
          <div className="glass-panel p-6 h-[300px] flex flex-col">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Activity size={18} className="text-primary-400" />
              System Health (CPU / Memory)
            </h3>
            <div className="flex-1 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b313d" vertical={false} />
                  <XAxis dataKey="time" stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#6b7280" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#16191f', borderColor: '#2b313d', borderRadius: '8px', color: '#fff' }}
                    itemStyle={{ color: '#60a5fa' }}
                  />
                  <Line type="monotone" dataKey="cpu" stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
                  <Line type="monotone" dataKey="memory" stroke="#8b5cf6" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Cost Insights Panel */}
          <div className="glass-panel flex flex-col overflow-hidden border-green-500/30 shadow-[0_0_15px_rgba(34,197,94,0.1)]">
            <div className="bg-green-500/10 px-6 py-4 flex items-center justify-between border-b border-green-500/20">
              <div className="flex items-center gap-2 text-green-400 font-semibold">
                <TrendingDown size={20} />
                FinOps & Cost Recommendations
              </div>
            </div>
            <div className="p-6 flex flex-col gap-6">
              {/* Table of costs */}
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-gray-400 uppercase border-b border-dark-600">
                    <tr>
                      <th className="py-2 font-medium">Namespace</th>
                      <th className="py-2 font-medium">Cost</th>
                      <th className="py-2 font-medium">Efficiency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-600/50">
                    {costInsights.map((ci) => (
                      <tr key={ci.id}>
                        <td className="py-2 text-gray-300">{ci.namespace}</td>
                        <td className="py-2 font-mono text-green-400">${ci.total_cost.toFixed(2)}</td>
                        <td className="py-2">
                          <div className="w-full bg-dark-600 rounded-full h-2 mt-1">
                            <div className="bg-primary-500 h-2 rounded-full" style={{ width: `${Math.min(ci.efficiency * 100, 100)}%` }}></div>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {costInsights.length === 0 && (
                      <tr>
                        <td colSpan="3" className="py-4 text-center text-gray-500">No cost data available</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              
              {/* AI Cost Recommendations */}
              {aiReport && aiReport.report_data.savings_recommendation && (
                <div className="bg-dark-900 p-4 rounded-lg border border-green-500/20 flex gap-4 items-start">
                  <div className="bg-green-500/10 p-2 rounded-lg text-green-400 mt-1">
                    <DollarSign size={20} />
                  </div>
                  <div>
                    <h4 className="text-gray-300 font-medium mb-1">AI Savings Recommendation</h4>
                    <p className="text-sm text-gray-400 leading-relaxed mb-2">
                      {aiReport.report_data.cost_insight}
                    </p>
                    <p className="text-sm text-green-400 font-medium leading-relaxed">
                      {aiReport.report_data.savings_recommendation}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-6 h-full">
          
          {/* Chaos Table */}
          <div className="glass-panel flex flex-col flex-1 max-h-[400px]">
            <div className="px-6 py-4 border-b border-dark-600/50 flex justify-between items-center">
              <h3 className="text-white font-medium flex items-center gap-2">
                <Database size={18} className="text-primary-400" />
                Chaos Experiments
              </h3>
            </div>
            <div className="p-0 overflow-auto flex-1">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-400 uppercase bg-dark-900/50 sticky top-0">
                  <tr>
                    <th className="px-6 py-3 font-medium">ID</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-600/50">
                  {chaosStatus.length > 0 ? chaosStatus.map((exp) => (
                    <tr key={exp.id} className="hover:bg-dark-600/20 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs text-gray-300">{exp.id}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          exp.status === 'FAILED' ? 'bg-danger-500/10 text-danger-400 border border-danger-500/20' : 
                          exp.status === 'RUNNING' ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20' :
                          'bg-success-500/10 text-success-400 border border-success-500/20'
                        }`}>
                          {exp.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-400">{exp.target_pod}</td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan="3" className="px-6 py-8 text-center text-gray-500">No experiments recorded</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Logs Viewer */}
          <div className="glass-panel flex flex-col flex-1 max-h-[400px]">
            <div className="px-6 py-4 border-b border-dark-600/50 flex justify-between items-center bg-dark-900/50">
              <h3 className="text-white font-medium flex items-center gap-2">
                <Terminal size={18} className="text-gray-400" />
                Live Logs (Loki)
              </h3>
            </div>
            <div className="p-4 bg-[#0d0f12] overflow-auto flex-1 font-mono text-xs leading-relaxed">
              {logs.length > 0 ? (
                logs.map((log, i) => {
                  let colorClass = "text-gray-400";
                  if (log.toLowerCase().includes("error") || log.toLowerCase().includes("fail")) colorClass = "text-danger-400";
                  if (log.toLowerCase().includes("warn")) colorClass = "text-yellow-400";
                  
                  return (
                    <div key={i} className={`whitespace-pre-wrap break-all mb-1 ${colorClass}`}>
                      {log}
                    </div>
                  );
                })
              ) : (
                <div className="text-gray-600 italic">Waiting for logs...</div>
              )}
            </div>
          </div>

        </div>
      </div>
      </>
      )}
    </div>
    </Show>
  </>
  );
}

export default App;
