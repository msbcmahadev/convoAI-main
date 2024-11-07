import "regenerator-runtime/runtime";
import { useState, useEffect, useRef } from "react";
import { FaMicrophoneAlt, FaStopCircle, FaStop } from "react-icons/fa";
import { GrSend } from "react-icons/gr";
import { motion } from "framer-motion";
import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";
import { Typewriter } from "react-simple-typewriter";
import Markdown from "react-markdown";
import AiCard from "../components/AiCard";
import { HOST, POCKETBASE } from "../../config";
import { Info } from "../utils/chatBotInfo";
import toTitleCase from "../utils/toTitleCase";
import toast from "react-hot-toast";

interface MessageProp {
  text: string;
  sender: string;
}

export default function Chatbot() {
  const [messages, setMessages] = useState<MessageProp[]>([]);
  const [prompt, setPrompt] = useState<string>("");
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const urlParams = new URLSearchParams(window.location.search);
  const company = urlParams.get("company");

  const [companyInfo, setCompanyInfo] = useState({
    id: "",
    vectorStoreId: "",
    assistantID: "",
    img: null,
    persona: "",
    customer_name: "",
  });

  if (!company) {
    window.location.href = "/form";
    return;
  }

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  useEffect(() => {
    let isMounted = true;

    const fetchCompanyData = async () => {
      try {
        const res = await fetch(`${HOST}/companies/${company}`);

        if (res.status == 404) {
          window.location.href = "/form";
          return;
        }

        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setCompanyInfo((prevInfo) => ({
              ...prevInfo,
              vectorStoreId: data.vector_store_id,
              assistantID: data.assistant_id,
              img: data.logo,
              persona: data.persona,
              customer_name: data.customer_name,
              id: data.id,
            }));
          }
        } else {
          window.location.href = "/form";
        }
      } catch (error) {
        console.error("Error fetching company data:", error);
      }
    };

    fetchCompanyData();

    return () => {
      isMounted = false;
    };
  }, [company]);
  const {
    finalTranscript,
    resetTranscript,
    listening,
    browserSupportsSpeechRecognition,
  } = useSpeechRecognition();

  if (!browserSupportsSpeechRecognition) {
    alert("Browser doesn't support speech recognition.");
  }

  useEffect(() => {
    if (finalTranscript !== "") {
      handleSendMessage(finalTranscript);
      setIsListening(false);
    }
  }, [finalTranscript]);

  const handleMicClick = () => {
    if (isListening) {
      SpeechRecognition.stopListening();
    } else {
      resetTranscript();
      SpeechRecognition.startListening({ continuous: false });
    }
    setIsListening((prev) => !prev);
  };

  const handleSendMessage = (inputPrompt: string) => {
    if (inputPrompt.trim() === "") return;

    const newMessage = { text: inputPrompt, sender: "user" };
    setMessages((prevMessages) => [...prevMessages, newMessage]);
    setPrompt("");
    resetTranscript();
    setIsProcessing(true);

    const controller = new AbortController();
    setAbortController(controller);

    fetch(`${HOST}/ask`, {
      method: "POST",
      body: JSON.stringify({
        prompt: inputPrompt,
        company_name: company,
        persona: companyInfo.persona,
      }),
      headers: {
        "Content-Type": "application/json",
      },
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) {
          toast.error("Something went wrong!");
          throw new Error("Network response was not ok");
        }
        return res.json();
      })
      .then((data) => {
        const aiMessage = { text: data.answer, sender: "ai" };
        setMessages((prev) => [...prev, aiMessage]);
        setIsProcessing(false);
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          console.log("Fetch request was aborted");
        } else {
          console.error("Fetch error:", error);
        }
      })
      .finally(() => {
        setIsProcessing(false);
      });
  };

  const handleCancelProcessing = () => {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
    }
    setIsProcessing(false);
  };

  return (
    <main className="h-screen grid grid-cols-[12vw_1fr] font-mont max-md:grid-cols-1 w-screen">
      <aside className="flex flex-col py-6 px-4 border-r items-center justify-between max-md:hidden">
        <img
          src={`${POCKETBASE}/api/files/companies/${companyInfo.id}/${companyInfo.img}`}
          alt="Company Logo"
          className="w-40 m-2"
        />
        <div className="w-full bg-fill/[0.1] h-14 rounded-md border gap-4 flex items-center px-2">
          <div className="size-10 bg-fill rounded-full"></div>
          <div>
            <p className="font-semibold text-[2vw] sm:text-[0.4vw] md:text-[0.5vw] lg:text-[0.6vw] xl:text-[0.8vw] flex">
              {companyInfo.customer_name}
            </p>
            <p className="text-[2vw] sm:text-[0.3vw] md:text-[0.4vw] lg:text-[0.5vw] xl:text-[0.6vw]">
              Customer
            </p>
          </div>
        </div>
      </aside>

      <section className="px-56 bg-slate-100 relative max-md:px-10">
        <div className="py-10 flex flex-col items-center h-screen">
          {messages.length === 0 ? (
            <>
              <p className="font-bold text-3xl py-4 px-8 max-md:px-4 max-md:py-2 max-md:text-xl text-primary bg-white rounded-full border">
                {toTitleCase(company.split("_").join(" "))} AI
              </p>
              <motion.div
                className="text-3xl font-medium mt-8 max-md:mt-3 opacity-80 max-md:text-lg"
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: { opacity: 0, y: 20 },
                  visible: {
                    opacity: 1,
                    y: 0,
                    transition: {
                      duration: 0.5,
                    },
                  },
                }}
              >
                Good Day, How may I help you?
              </motion.div>
              <img
                src={`${POCKETBASE}/api/files/companies/${companyInfo.id}/${companyInfo.img}`}
                alt="Company Logo"
                className="mt-32 w-56 md:hidden"
              />
              <motion.div
                className="grid grid-cols-2 w-full gap-x-6 gap-y-10 pt-10 max-md:hidden"
                initial="hidden"
                animate="visible"
                variants={{
                  hidden: { opacity: 0 },
                  visible: {
                    opacity: 1,
                    transition: {
                      staggerChildren: 0.2,
                    },
                  },
                }}
              >
                {Info.map((card, index) => (
                  <motion.div
                    key={index}
                    variants={{
                      hidden: { opacity: 0, y: 20 },
                      visible: { opacity: 1, y: 0 },
                    }}
                    transition={{ duration: 0.5 }}
                  >
                    <AiCard
                      Icon={card.Icon}
                      title={card.title}
                      text={card.text}
                    />
                  </motion.div>
                ))}
              </motion.div>
            </>
          ) : (
            <div
              className="w-full flex flex-col gap-4 px-4 py-2 overflow-y-scroll mb-[5vh]"
              ref={containerRef}
            >
              {messages.map((msg, index) => (
                <div key={index} className="flex items-center">
                  {msg.sender === "user" ? (
                    <div className="flex flex-col ">
                      <p className="font-medium bg-white px-2 py-2 border rounded-full">
                        <Typewriter
                          words={[msg.text]}
                          typeSpeed={2}
                          cursorStyle={"|"}
                          delaySpeed={3}
                        />
                      </p>
                    </div>
                  ) : (
                    <div className="flex flex-col rounded-full">
                      <p className="font-medium mt-2">
                        <Markdown>{msg.text}</Markdown>
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-center items-end pb-4 overflow-hidden">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(prompt);
            }}
            className="bg-white rounded-full border flex items-center justify-between px-4 w-[90%] md:w-[60%] lg:w-[50%] max-w-[800px] py-2 h-16 fixed bottom-6"
          >
            <input
              type="text"
              className="rounded-full h-12 w-full focus:outline-none pl-4"
              placeholder="Ask me anything"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />

            <div className="flex items-center">
              {!isProcessing && (
                <FaMicrophoneAlt
                  className={`${
                    listening
                      ? "text-red-500 animate-pulse"
                      : "hover:text-slate-600 text-slate-500"
                  } text-2xl cursor-pointer transition-colors`}
                  onClick={handleMicClick}
                />
              )}
              {!isProcessing && (
                <>
                  {isListening ? (
                    <FaStopCircle
                      className="text-red-500 text-2xl ml-4 cursor-pointer hover:text-red-600 transition-colors"
                      onClick={handleMicClick}
                    />
                  ) : (
                    <GrSend
                      className="text-slate-500 text-2xl ml-4 hover:text-slate-600 cursor-pointer transition-colors"
                      onClick={() => handleSendMessage(prompt)}
                    />
                  )}
                </>
              )}

              {isProcessing && (
                <FaStop
                  className="text-slate-500 text-2xl ml-4 hover:text-slate-600 cursor-pointer transition-colors animate-pulse"
                  onClick={handleCancelProcessing}
                />
              )}
            </div>
          </form>
        </div>
      </section>
    </main>
  );
}
