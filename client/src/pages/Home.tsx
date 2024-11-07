import Ellipse1 from "../assets/images/Ellipse1.svg";
import Ellipse2 from "../assets/images/Ellipse2.svg";
import Ellipse3 from "../assets/images/Ellipse3.svg";
import Ellipse4 from "../assets/images/Ellipse4.svg";
import Header from "../components/Header";
import { useEffect, useState } from "react";
import { HOST } from "../../config";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

function formatCompanyName(name: string) {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function formatDate(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    hour12: true,
  });
}

function ScrapedCompanyCard({ company }: { company: any }) {
  const navigate = useNavigate();
  const handleDelete = () => {
    const deletePromise = fetch(`${HOST}/companies/${company.company_name}`, {
      method: "DELETE",
    });

    toast
      .promise(deletePromise, {
        loading: "Deleting...",
        success: (data) => {
          if (data.ok) {
            //@ts-ignore
            return data.detail;
          }
          throw new Error("Failed to delete company");
        },
        error: "Error deleting the company",
      })
      .then((data) => {
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      })
      .catch((error) => {
        console.error(error);
        toast.error(JSON.stringify(error));
      });
  };
  return (
    <div
      className="px-4 py-4 font-bold border text-lg rounded-md hover:bg-slate-100 transition-colors hover:cursor-pointer flex items-center gap-4"
      onClick={() => navigate(`/chatbot?company=${company.company_name}`)}
    >
      <div>
        <h2 className="text-xl font-bold">
          {formatCompanyName(company.company_name)}
        </h2>

        <p className="text-xs opacity-50 italic">
          Scraped on: {formatDate(company.created)}
        </p>
        <button
          className="text-xs bg-red-500 text-white font-bold mt-2 hover:bg-red-600 transition-colors"
          title="This action is irreversible!"
          onClick={(e) => {
            e.stopPropagation();
            handleDelete();
          }}
        >
          Delete Company
        </button>
      </div>
    </div>
  );
}

export default function Home() {
  const [companies, setCompanies] = useState([]);
  const navigate = useNavigate();
  useEffect(() => {
    fetch(`${HOST}/companies`)
      .then((res) => res.json())
      .then((data) => setCompanies(data));
  }, []);
  return (
    <div className="h-screen w-screen relative">
      <Header />
      <div className="image-section-rounded">
        <img
          src={Ellipse1}
          alt="Ellipse-1"
          className="absolute -z-10 bottom-0 right-0"
        />
        <img
          src={Ellipse2}
          alt="Ellipse-2"
          className="absolute -z-10 bottom-[50vh] right-24"
        />
        <img src={Ellipse3} alt="Ellipse-3" className="absolute -z-10" />
        <img
          src={Ellipse4}
          alt="Ellipse-4"
          className="absolute -z-10 left-[20vw]"
        />
      </div>
      <div className="h-full flex justify-center">
        <div className="min-w-[60vw] max-w-[80vw] flex flex-col items-center max-h-[50vh] py-24 mt-10 bg-white rounded-md border">
          <h1 className="text-2xl font-bold ">Use Already Scraped Websites</h1>
          {companies.length == 0 && (
            <div className="text-center mt-2">
              No companies found! Start by building a chatbot first!
            </div>
          )}
          <div className="grid grid-cols-3 gap-x-2 mt-4 gap-y-2">
            {companies.map((cmp) => (
              //@ts-ignore
              <ScrapedCompanyCard company={cmp} key={cmp.id} />
            ))}
          </div>
          <button
            className="text-sm font-bold mt-10 bg-black text-white border-md hover:bg-[#1e1e1e] hover:shadow-md"
            onClick={() => navigate("/form")}
          >
            Create your own personalised chatbot
          </button>
        </div>
      </div>
    </div>
  );
}
