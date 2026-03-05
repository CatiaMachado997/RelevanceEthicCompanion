'use client';

import { useState, useEffect, useRef } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Send, Bot, User, AlertTriangle, CheckCircle, XCircle, Sparkles } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  esl_decision?: {
    status: 'APPROVED' | 'VETOED' | 'MODIFIED';
    reason: string;
    violated_values?: string[];
  };
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load chat history on mount
  useEffect(() => {
    loadHistory();
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    try {
      const history = await api.chat.history();
        // Transform API response to match Message interface
        const transformedMessages = (history.messages || []).map((msg, idx) => ({
          id: `${Date.now()}-${idx}`,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: msg.timestamp,
        }));
        setMessages(transformedMessages);
    } catch (error) {
      console.error('Failed to load chat history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.chat.send(input);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response || 'No response received',
        timestamp: new Date().toISOString(),
        esl_decision: response.esl_decision,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error connecting to the backend. Please ensure the backend is running.',
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (loadingHistory) {
    return (
      <div className="space-y-4 p-4 max-w-4xl mx-auto">
        {[1, 2, 3].map((i) => (
            <div key={i} className={`flex gap-3 ${i % 2 === 0 ? 'flex-row-reverse' : ''}`}>
                <Skeleton className="h-10 w-10 rounded-full" />
                <Skeleton className="h-20 w-[60%] rounded-lg" />
            </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-background">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-6 p-8 opacity-0 animate-[fadeIn_0.5s_ease-in_forwards]">
            <div className="bg-primary/10 p-6 rounded-full">
                <Bot className="h-12 w-12 text-primary" />
            </div>
            <div className="space-y-2">
                <h2 className="text-2xl font-bold tracking-tight">Start a Conversation</h2>
                <p className="text-muted-foreground max-w-md">
                    Ask me anything! I'm here to assist you while respecting your boundaries.
                </p>
            </div>
            <Card className="max-w-md w-full text-left bg-muted/50 border-dashed">
                <CardContent className="pt-6">
                    <div className="flex items-center gap-2 font-semibold mb-3 text-sm text-muted-foreground">
                        <Sparkles className="h-4 w-4" />
                        Example prompts
                    </div>
                    <ul className="space-y-2 text-sm">
                        <li className="p-2 hover:bg-background rounded-md cursor-pointer transition-colors" onClick={() => setInput("Summarize my upcoming meetings")}>• "Summarize my upcoming meetings"</li>
                        <li className="p-2 hover:bg-background rounded-md cursor-pointer transition-colors" onClick={() => setInput("Help me prioritize my goals")}>• "Help me prioritize my goals"</li>
                        <li className="p-2 hover:bg-background rounded-md cursor-pointer transition-colors" onClick={() => setInput("What should I focus on today?")}>• "What should I focus on today?"</li>
                    </ul>
                </CardContent>
            </Card>
          </div>
        ) : (
          <div className="space-y-6 max-w-4xl mx-auto">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-4 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role === 'assistant' && (
                    <Avatar className="h-8 w-8 mt-1">
                        <AvatarFallback className="bg-primary/10 text-primary"><Bot className="h-4 w-4" /></AvatarFallback>
                    </Avatar>
                )}

                <div className={`flex flex-col max-w-[80%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div
                    className={`rounded-2xl px-5 py-3 shadow-sm ${
                        message.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-br-sm'
                        : 'bg-card border rounded-bl-sm'
                    }`}
                    >
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
                    </div>

                    {/* ESL Decision Badge */}
                    {message.esl_decision && (
                        <div className="mt-2 text-xs">
                           <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${
                                message.esl_decision.status === 'APPROVED'
                                    ? 'bg-green-50 text-green-700 border-green-200'
                                    : message.esl_decision.status === 'MODIFIED'
                                    ? 'bg-yellow-50 text-yellow-700 border-yellow-200'
                                    : 'bg-red-50 text-red-700 border-red-200'
                           }`}>
                                {message.esl_decision.status === 'APPROVED' && <CheckCircle className="h-3 w-3" />}
                                {message.esl_decision.status === 'MODIFIED' && <AlertTriangle className="h-3 w-3" />}
                                {message.esl_decision.status === 'VETOED' && <XCircle className="h-3 w-3" />}
                                <span className="font-medium">ESL: {message.esl_decision.reason}</span>
                           </div>
                        </div>
                    )}
                    
                    <span className="text-[10px] text-muted-foreground mt-1 px-1">
                        {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                </div>

                {message.role === 'user' && (
                    <Avatar className="h-8 w-8 mt-1">
                        <AvatarFallback className="bg-slate-200"><User className="h-4 w-4 text-slate-600" /></AvatarFallback>
                    </Avatar>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 p-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-4 items-end">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message... (Press Enter to send, Shift+Enter for new line)"
              className="min-h-[60px] resize-none"
              disabled={loading}
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              size="icon"
              className="h-[60px] w-[60px] shrink-0 rounded-xl"
            >
              {loading ? (
                 <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                <Send className="h-6 w-6" />
              )}
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground mt-2 text-center">
            Your messages are protected by the Ethical Safeguard Layer
          </p>
        </div>
      </div>
    </div>
  );
}