"use client";

import Image from "next/image";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { createFeedback, createInterviewDocument, saveInterviewTranscript } from "@/lib/actions/general.action";

enum CallStatus {
  INACTIVE = "INACTIVE",
  CONNECTING = "CONNECTING",
  ACTIVE = "ACTIVE",
  FINISHED = "FINISHED",
}

interface SavedMessage {
  role: "user" | "system" | "assistant";
  content: string;
}

const Agent = ({
  userName,
  userId,
  interviewId,
  feedbackId,
  type,
  questions,
  role,
  level,
  techstack,
  interviewType,
}: AgentProps) => {
  const router = useRouter();
  const [callStatus, setCallStatus] = useState<CallStatus>(CallStatus.INACTIVE);
  const [messages, setMessages] = useState<SavedMessage[]>([]);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [lastMessage, setLastMessage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeInterviewId, setActiveInterviewId] = useState<string | undefined>(interviewId);

  // Stop flag for the interview loop
  const shouldStopRef = useRef<boolean>(false);

  useEffect(() => {
    if (messages.length > 0) {
      setLastMessage(messages[messages.length - 1].content);
    }

    const handleGenerateFeedback = async (messages: SavedMessage[]) => {
      console.log("handleGenerateFeedback");

      const { success, feedbackId: id } = await createFeedback({
        interviewId: activeInterviewId!,
        userId: userId!,
        transcript: messages,
        feedbackId,
      });

      if (success && id) {
        router.push(`/interview/${activeInterviewId}/feedback`);
      } else {
        console.log("Error saving feedback");
        router.push("/");
      }
    };

    if (callStatus === CallStatus.FINISHED) {
      if (type === "generate") {
        router.push("/");
      } else {
        // Persist transcript to interview doc for history (voice-based)
        if (activeInterviewId && userId) {
          saveInterviewTranscript({
            interviewId: activeInterviewId,
            userId,
            transcript: messages,
            voiceBased: true,
          });
        }
        handleGenerateFeedback(messages);
      }
    }
  }, [messages, callStatus, feedbackId, activeInterviewId, router, type, userId]);

  const handleCall = async () => {
    setErrorMessage(null);
    shouldStopRef.current = false;
    setCallStatus(CallStatus.CONNECTING);

    const baseUrl =
      process.env.NEXT_PUBLIC_INTERVIEW_SERVER_URL || "http://localhost:5000";

    const postJson = async (url: string, body?: unknown) => {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed: ${res.status}`);
      }
      return res.json();
    };

    const getJson = async (url: string) => {
      const res = await fetch(url);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed: ${res.status}`);
      }
      return res.json();
    };

    try {
      // Ensure we have an interview document id for history/feedback
      let currentInterviewId = activeInterviewId;
      if (!currentInterviewId && userId) {
        const created = await createInterviewDocument({
          userId,
          type: "custom",
          questions: questions || [],
        });
        if (created.success && created.interviewId) {
          currentInterviewId = created.interviewId;
          setActiveInterviewId(created.interviewId);
        }
      }

      // Prepare interview data to send to backend
      const interviewData: any = {};
      if (role) interviewData.role = role;
      if (level) interviewData.level = level;
      if (techstack) interviewData.techstack = techstack;
      if (interviewType) interviewData.type = interviewType;
      if (questions) interviewData.questions = questions;

      // Start interview session with interview data
      const startData = await postJson(
        `${baseUrl}/api/start-interview`,
        Object.keys(interviewData).length > 0 ? interviewData : undefined
      );
      const sessionId: string = startData.session_id;
      const firstMessage: string = startData.message;

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: firstMessage },
      ]);
      // Speak assistant message in the browser
      try {
        if (typeof window !== "undefined" && "speechSynthesis" in window) {
          const utterance = new SpeechSynthesisUtterance(firstMessage);
          utterance.onstart = () => setIsSpeaking(true);
          utterance.onend = () => setIsSpeaking(false);
          window.speechSynthesis.speak(utterance);
        }
      } catch {}
      setCallStatus(CallStatus.ACTIVE);

      // Main loop: listen via STT -> respond -> until completed or stopped
      // eslint-disable-next-line no-constant-condition
      while (true) {
        if (shouldStopRef.current) break;

        // Ask server to listen for user speech
        let userInput: string | null = null;
        // Try a few times before falling back to manual input
        for (let attempt = 0; attempt < 3 && !userInput; attempt++) {
          try {
            const sttData = await getJson(`${baseUrl}/stt`);
            if (sttData?.status === "ok" && sttData?.transcription) {
              userInput = sttData.transcription as string;
              break;
            }
          } catch (e) {
            console.warn("STT attempt failed", e);
          }
          // small delay before next attempt
          await new Promise((r) => setTimeout(r, 800));
          if (shouldStopRef.current) break;
        }

        if (!userInput) {
          // Manual fallback
          userInput = window.prompt("Type your response (mic unavailable):") || "";
          if (!userInput) {
            // If still empty, retry loop
            continue;
          }
        }

        setMessages((prev) => [
          ...prev,
          { role: "user", content: userInput! },
        ]);

        const respond = await postJson(`${baseUrl}/api/respond`, {
          session_id: sessionId,
          response: userInput,
        });

        const assistantMessage: string = respond.message;
        const completed: boolean = respond.status === "completed";

        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: assistantMessage },
        ]);
        // Speak assistant message in the browser
        try {
          if (typeof window !== "undefined" && "speechSynthesis" in window) {
            const utterance = new SpeechSynthesisUtterance(assistantMessage);
            utterance.onstart = () => setIsSpeaking(true);
            utterance.onend = () => setIsSpeaking(false);
            window.speechSynthesis.speak(utterance);
          }
        } catch {}

        if (completed) {
          break;
        }
      }

      setCallStatus(CallStatus.FINISHED);
    } catch (error: any) {
      const message =
        error?.response?.data?.message ||
        error?.response?.data ||
        error?.data?.message ||
        error?.message ||
        "Failed to start interview.";
      console.error(message);
      setErrorMessage(message);
      setCallStatus(CallStatus.INACTIVE);
    }
  };

  const handleDisconnect = () => {
    shouldStopRef.current = true;
    setCallStatus(CallStatus.FINISHED);
  };

  return (
    <>
      <div className="call-view">
        {/* AI Interviewer Card */}
        <div className="card-interviewer">
          <div className="avatar">
            <Image
              src="/ai-avatar.png"
              alt="profile-image"
              width={65}
              height={54}
              className="object-cover"
            />
            {isSpeaking && <span className="animate-speak" />}
          </div>
          <h3>AI Interviewer</h3>
        </div>

        {/* User Profile Card */}
        <div className="card-border">
          <div className="card-content">
            <Image
              src="/user-avatar.png"
              alt="profile-image"
              width={539}
              height={539}
              className="rounded-full object-cover size-[120px]"
            />
            <h3>{userName}</h3>
          </div>
        </div>
      </div>

      {messages.length > 0 && (
        <div className="transcript-border">
          <div className="transcript">
            <p
              key={lastMessage}
              className={cn(
                "transition-opacity duration-500 opacity-0",
                "animate-fadeIn opacity-100"
              )}
            >
              {lastMessage}
            </p>
          </div>
        </div>
      )}

      <div className="w-full flex justify-center">
        {callStatus !== "ACTIVE" ? (
          <button
            className="relative btn-call"
            onClick={() => handleCall()}
            disabled={callStatus === "CONNECTING"}
            aria-busy={callStatus === "CONNECTING"}
          >
            <span
              className={cn(
                "absolute animate-ping rounded-full opacity-75",
                callStatus !== "CONNECTING" && "hidden"
              )}
            />

            <span className="relative">
              {callStatus === "INACTIVE" || callStatus === "FINISHED"
                ? "Call"
                : ". . ."}
            </span>
          </button>
        ) : (
          <button className="btn-disconnect" onClick={() => handleDisconnect()}>
            End
          </button>
        )}
      </div>

      {/* Download Transcript PDF */}
      {messages.length > 0 && (
        <div className="w-full flex justify-center mt-4">
          <button
            className="btn-call"
            onClick={async () => {
              try {
                const { jsPDF } = await import("jspdf");
                const doc = new jsPDF();
                const title = `Interview Transcript${userName ? ` - ${userName}` : ""}`;
                doc.setFontSize(14);
                doc.text(title, 10, 10);
                doc.setFontSize(11);

                const lines: string[] = [];
                messages.forEach((m, idx) => {
                  lines.push(`${idx + 1}. ${m.role.toUpperCase()}: ${m.content}`);
                });

                // Simple text wrapping
                const pageWidth = doc.internal.pageSize.getWidth() - 20;
                let y = 20;
                for (const line of lines) {
                  const split = doc.splitTextToSize(line, pageWidth);
                  for (const s of split) {
                    if (y > doc.internal.pageSize.getHeight() - 20) {
                      doc.addPage();
                      y = 20;
                    }
                    doc.text(s, 10, y);
                    y += 7;
                  }
                }

                const filename = `interview-transcript-${new Date()
                  .toISOString()
                  .replace(/[:.]/g, "-")}.pdf`;
                doc.save(filename);
              } catch (e) {
                console.error("Failed to generate PDF", e);
              }
            }}
          >
            Download Transcript PDF
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="w-full flex justify-center mt-3">
          <p className="text-destructive-100 text-sm">{errorMessage}</p>
        </div>
      )}
    </>
  );
};

export default Agent;