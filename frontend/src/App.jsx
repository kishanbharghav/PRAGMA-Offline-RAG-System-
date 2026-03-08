import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
    FileUp,
    MessageSquare,
    ShieldCheck,
    Send,
    FileText,
    Server,
    Loader2,
    Database
} from 'lucide-react';

const App = () => {
    const [documents, setDocuments] = useState([]);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [serverStatus, setServerStatus] = useState('checking'); // checking, online, offline
    const messagesEndRef = useRef(null);

    const API_BASE = 'http://localhost:8000';

    useEffect(() => {
        checkServerHealth();
        fetchDocuments();
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, isTyping]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    const checkServerHealth = async () => {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (res.ok) {
                setServerStatus('online');
            } else {
                setServerStatus('offline');
            }
        } catch (e) {
            setServerStatus('offline');
        }
    };

    const fetchDocuments = async () => {
        try {
            const res = await fetch(`${API_BASE}/documents`);
            const data = await res.json();
            setDocuments(data.documents || []);
        } catch (e) {
            console.error("Failed to fetch documents", e);
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch(`${API_BASE}/ingest`, {
                method: 'POST',
                body: formData,
            });

            if (res.ok) {
                await fetchDocuments();
                // Add a system welcome message for the new doc
                setMessages(prev => [...prev, {
                    role: 'system',
                    content: `Successfully securely ingested **${file.name}**. It is now ready for query.`
                }]);
            }
        } catch (e) {
            console.error("Upload failed", e);
            setMessages(prev => [...prev, {
                role: 'system',
                content: `❌ Failed to ingest ${file.name}. Please check if the backend is running.`
            }]);
        } finally {
            setIsUploading(false);
        }
    };

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim() || isTyping || documents.length === 0) return;

        const userMessage = input;
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setIsTyping(true);

        // Add an empty assistant message to stream into
        setMessages(prev => [...prev, { role: 'assistant', content: '', pages: [], entities: null }]);

        try {
            const res = await fetch(`${API_BASE}/query_stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userMessage })
            });

            if (!res.body) throw new Error("No response body");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n').filter(line => line.trim() !== '');

                for (const line of lines) {
                    try {
                        const data = JSON.parse(line);

                        if (data.type === 'metadata') {
                            setMessages(prev => {
                                const newMessages = [...prev];
                                const lastMsg = newMessages[newMessages.length - 1];
                                lastMsg.pages = data.pages;
                                lastMsg.entities = data.entities;
                                return newMessages;
                            });
                        } else if (data.type === 'chunk') {
                            setMessages(prev => {
                                const newMessages = [...prev];
                                const lastIndex = newMessages.length - 1;
                                newMessages[lastIndex] = {
                                    ...newMessages[lastIndex],
                                    content: newMessages[lastIndex].content + data.content
                                };
                                return newMessages;
                            });
                        }
                    } catch (err) {
                        console.error("Error parsing NDJSON line:", line, err);
                    }
                }
            }
        } catch (e) {
            console.error("Stream failed", e);
            setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                lastMsg.content = "I encountered an error connecting to the private AI. Please ensure the backend and Ollama are running.";
                return newMessages;
            });
        } finally {
            setIsTyping(false);
        }
    };

    return (
        <div className="flex h-screen w-full bg-[#0f172a] text-slate-200 overflow-hidden font-sans">

            {/* Sidebar - Data Control */}
            <div className="w-80 border-r border-slate-700/50 bg-[#1e293b]/40 backdrop-blur-xl flex flex-col shadow-2xl z-10">
                <div className="p-6 border-b border-slate-700/50">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-xl bg-teal-500/20 flex items-center justify-center border border-teal-500/30">
                            <ShieldCheck className="text-teal-400" size={24} />
                        </div>
                        <div>
                            <h1 className="text-xl font-bold text-white tracking-tight">DocuVault</h1>
                            <span className="text-xs text-teal-400 font-medium tracking-wide uppercase flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse"></span>
                                Secure Environment
                            </span>
                        </div>
                    </div>
                </div>

                <div className="p-6 flex-1 overflow-y-auto">
                    <div className="mb-6">
                        <h2 className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-3">Storage Engine</h2>
                        <div className="glass-panel rounded-xl p-4 flex flex-col gap-3">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-sm text-slate-300">
                                    <Server size={16} className={serverStatus === 'online' ? 'text-teal-400' : 'text-rose-400'} />
                                    Local API Node
                                </div>
                                {serverStatus === 'checking' ? (
                                    <span className="text-xs bg-slate-700/50 text-slate-300 px-2.5 py-1 rounded-full border border-slate-600/50 flex flex-center gap-1">
                                        <Loader2 size={12} className="animate-spin" /> Ping...
                                    </span>
                                ) : serverStatus === 'online' ? (
                                    <span className="text-xs bg-teal-500/10 text-teal-400 px-2.5 py-1 rounded-full border border-teal-500/20">Online</span>
                                ) : (
                                    <span className="text-xs bg-rose-500/10 text-rose-400 px-2.5 py-1 rounded-full border border-rose-500/20">Offline</span>
                                )}
                            </div>
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-sm text-slate-300">
                                    <Database size={16} className="text-indigo-400" />
                                    ChromaDB Vector
                                </div>
                                <span className="text-xs bg-indigo-500/10 text-indigo-400 px-2.5 py-1 rounded-full border border-indigo-500/20">Active</span>
                            </div>
                        </div>
                    </div>

                    <div className="mb-4">
                        <div className="flex items-center justify-between mb-3">
                            <h2 className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Indexed Archives</h2>
                            <span className="text-xs bg-slate-700/50 text-slate-300 px-2 py-0.5 rounded-full">{documents.length}</span>
                        </div>

                        <label className={`block relative group cursor-pointer w-full p-6 border-2 border-dashed ${isUploading ? 'border-teal-500/50 bg-teal-500/5' : 'border-slate-700 hover:border-teal-500/50 hover:bg-slate-800/50'} rounded-xl transition-all duration-300 ease-out mb-4`}>
                            <input
                                type="file"
                                accept=".pdf"
                                className="hidden"
                                onChange={handleFileUpload}
                                disabled={isUploading}
                            />
                            <div className="flex flex-col items-center text-center gap-2">
                                {isUploading ? (
                                    <Loader2 className="animate-spin text-teal-400 mb-1" size={28} />
                                ) : (
                                    <FileUp className="text-slate-500 group-hover:text-teal-400 transition-colors mb-1" size={28} />
                                )}
                                <span className="text-sm font-medium text-slate-300 group-hover:text-white transition-colors">
                                    {isUploading ? 'Ingesting vectors...' : 'Upload PDF Archive'}
                                </span>
                                <span className="text-xs text-slate-500">Local encryption only</span>
                            </div>
                        </label>

                        <div className="flex flex-col gap-2">
                            {documents.length === 0 ? (
                                <div className="text-sm text-slate-500 italic p-4 text-center border border-slate-800 rounded-lg">
                                    No documents found in the local vector vault.
                                </div>
                            ) : (
                                documents.map((doc, idx) => (
                                    <div key={idx} className="flex items-center gap-3 p-3 bg-slate-800/40 border border-slate-700/50 rounded-lg hover:bg-slate-800/80 transition-colors group">
                                        <FileText size={18} className="text-indigo-400" />
                                        <span className="text-sm text-slate-300 truncate font-medium flex-1">{doc.filename}</span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Interface - Chat Engine */}
            <div className="flex-1 flex flex-col relative bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-opacity-5">

                {/* Subtle background gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-b from-[#0f172a] via-[#0f172a]/95 to-[#1e293b] pointer-events-none z-0"></div>

                {/* Header */}
                <header className="h-16 border-b border-slate-800 flex items-center px-8 z-10 glass">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></div>
                        <span className="text-sm font-medium text-slate-300">Llama3 Local Inference Engine</span>
                    </div>
                </header>

                {/* Message Thread */}
                <div className="flex-1 overflow-y-auto p-4 md:p-8 z-10 w-full max-w-5xl mx-auto flex flex-col relative scroll-smooth">

                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full opacity-60">
                            <MessageSquare size={48} className="text-slate-600 mb-6" />
                            <h2 className="text-2xl font-bold text-slate-300 mb-2">Private Query Interface</h2>
                            <p className="text-slate-500 max-w-md text-center">
                                Your data never leaves this machine. Upload a document to the vault and ask questions.
                            </p>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-6 pb-20">
                            {messages.map((msg, index) => (
                                <div
                                    key={index}
                                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in-up`}
                                >
                                    <div className={`
                    max-w-[85%] rounded-2xl p-5 shadow-sm
                    ${msg.role === 'user'
                                            ? 'bg-teal-600/90 text-white rounded-br-none border border-teal-500/50 backdrop-blur-md'
                                            : msg.role === 'system'
                                                ? 'bg-slate-800/80 text-emerald-400 border border-emerald-500/20 text-sm font-mono mx-auto rounded-xl backdrop-blur-md'
                                                : 'glass-panel rounded-bl-none prose text-slate-200'}
                  `}>
                                        {msg.role === 'assistant' ? (
                                            <div className="flex flex-col gap-3">
                                                <div className="flex items-center gap-2 mb-1 border-b border-slate-700/50 pb-2">
                                                    <MessageSquare size={14} className="text-indigo-400" />
                                                    <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">DocuVault AI</span>
                                                </div>

                                                <div className="prose prose-invert max-w-none text-[15px] leading-relaxed">
                                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                </div>

                                                {/* Citations & Discovered Entities */}
                                                {(msg.pages?.length > 0 || msg.entities) && (
                                                    <div className="mt-4 pt-3 border-t border-slate-700/50 flex flex-wrap gap-2 text-xs">
                                                        {/* We removed the explicit page list because the LLM natively cites sources now */}

                                                        {msg.entities?.emails?.length > 0 && (
                                                            <div className="flex items-center gap-1.5 bg-emerald-500/10 text-emerald-300 px-2.5 py-1.5 rounded-md border border-emerald-500/20">
                                                                <span>📧 {msg.entities.emails.join(', ')}</span>
                                                            </div>
                                                        )}

                                                        {msg.entities?.urls?.length > 0 && (
                                                            <div className="flex items-center gap-1.5 bg-blue-500/10 text-blue-300 px-2.5 py-1.5 rounded-md border border-blue-500/20">
                                                                <span>🔗 Found Links</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        ) : msg.role === 'system' ? (
                                            <ReactMarkdown>{msg.content}</ReactMarkdown>
                                        ) : (
                                            msg.content
                                        )}
                                    </div>
                                </div>
                            ))}

                            {isTyping && messages[messages.length - 1]?.role !== 'assistant' && (
                                <div className="flex justify-start">
                                    <div className="bg-slate-800/80 backdrop-blur-md rounded-2xl rounded-bl-none p-4 flex items-center gap-2 border border-slate-700/50">
                                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                        <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="p-4 md:p-6 bg-gradient-to-t from-[#0f172a] directly to-transparent z-10 w-full max-w-5xl mx-auto">
                    <form
                        onSubmit={handleSend}
                        className="flex relative bg-[#1e293b]/70 backdrop-blur-xl border border-slate-600/50 rounded-2xl shadow-2xl overflow-hidden focus-within:border-teal-500/50 focus-within:ring-1 focus-within:ring-teal-500/50 transition-all duration-300"
                    >
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder={documents.length === 0 ? "Upload an archive to begin..." : "Ask a query about your documents..."}
                            disabled={documents.length === 0 || isTyping}
                            className="flex-1 bg-transparent text-slate-100 placeholder-slate-400 text-[15px] p-5 focus:outline-none disabled:opacity-50"
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || documents.length === 0 || isTyping}
                            className="px-6 py-4 m-1 rounded-xl bg-teal-600 hover:bg-teal-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium transition-colors flex items-center justify-center disabled:cursor-not-allowed group"
                        >
                            <Send size={18} className="group-hover:translate-x-1 transition-transform" />
                        </button>
                    </form>
                    <div className="text-center mt-3 flex items-center justify-center gap-2 text-xs text-slate-500 font-medium">
                        <ShieldCheck size={14} className="text-emerald-500/70" />
                        Local processing only. Responses are synthesized by Llama3.
                    </div>
                </div>

            </div>

        </div>
    );
};

export default App;
