from db import client as db
from fastapi import (
    FastAPI,
    status,
    Response,
    Form,
    UploadFile,
    BackgroundTasks,
    HTTPException,
    File,
    Body,
)
from fastapi.middleware.cors import CORSMiddleware
from utils import (
    create_vector_store,
    create_assistant,
    validate_website,
    scrap_website,
    process_stream_event,
    scraping_status,
    session_manager,
    upload_pdf_to_vector_store,
    convert_docx_to_pdf,
    convert_markdown_to_pdf,
    convert_markdown_to_pdf_vs,
    delete_assistant_and_vs,
    fetch_or_upload_logo,
    logger,
)
from openai import Client
from dotenv import load_dotenv
from pocketbase.client import ClientResponseError, FileUpload
from typing import Optional
from datetime import datetime
import uvicorn
import asyncio
from queue import Queue
from multiprocessing import Process, Queue
import os

load_dotenv()
app = FastAPI()

# ? Creating Temporary Folders
markdown_folder = os.path.join(os.getcwd(), "temp", "markdown")
attachments_folder = os.path.join(os.getcwd(), "temp", "attachments")
converted_pdfs_folder = os.path.join(os.getcwd(), "temp", "pdf")

os.makedirs(markdown_folder, exist_ok=True)
os.makedirs(attachments_folder, exist_ok=True)
os.makedirs(converted_pdfs_folder, exist_ok=True)
# ?


ai = Client()
total_scraped_companies = 0

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def scrap_website_process(url, company_name, result_queue):
    try:

        start_time = datetime.now()
        logger.info(f"Started scraping {url} for {company_name} at {start_time}")

        scrap_website(url, company_name)

        end_time = datetime.now()
        time_taken = (end_time - start_time).total_seconds()
        logger.info(
            f"Completed scraping {url} for {company_name} at {end_time}, time taken: {time_taken} seconds"
        )

        result_queue.put(("Completed", time_taken))
    except Exception as e:
        logger.error(f"Error scraping {url} for {company_name}: {e}")
        result_queue.put((f"Failed: {str(e)}", None))


async def run_scraping_task(
    company_name: str, websites: list[str], vector_store_id: str, timeout_seconds: int
):
    global total_scraped_companies
    total_scraped_companies = 0
    scraping_status[company_name] = {}
    logger.info(f"Starting Scraping Session with Timeout at {timeout_seconds} seconds")

    for url in websites:
        start_time = datetime.now()
        logger.info(f"Task started for {url} at {start_time}")

        try:
            scraping_status[company_name][url] = {
                "status": "In Progress",
                "start_time": start_time,
                "elapsed": 0,
            }

            result_queue = Queue()
            process = Process(
                target=scrap_website_process, args=(url, company_name, result_queue)
            )
            process.start()

            for _ in range(timeout_seconds):
                if process.is_alive():
                    await asyncio.sleep(1)
                else:
                    break
            else:
                if process.is_alive():
                    logger.info(
                        f"Attempting to terminate process with PID {process.pid}"
                    )
                    process.terminate()
                    process.join(timeout=1)

                if process.is_alive():
                    logger.info(f"Force killing process with PID {process.pid}")
                    process.kill()

                scraping_status[company_name][url]["status"] = "Timed Out"
                total_scraped_companies += 1
                end_time = datetime.now()
                scraping_status[company_name][url]["end_time"] = end_time
                time_taken = (end_time - start_time).total_seconds()
                scraping_status[company_name][url]["elapsed"] = time_taken
                logger.info(
                    f"Scraping {url} for {company_name} timed out after {timeout_seconds} seconds"
                )

            process.join()
            if not result_queue.empty():
                result, child_time_taken = result_queue.get()
                if result == "Completed":
                    scraping_status[company_name][url]["status"] = "Completed"
                    total_scraped_companies += 1
                    time_taken = (
                        child_time_taken
                        if child_time_taken is not None
                        else (datetime.now() - start_time).total_seconds()
                    )
                    scraping_status[company_name][url]["elapsed"] = time_taken
                    logger.info(
                        f"Scraping {url} for {company_name} completed in {time_taken} seconds"
                    )
                else:
                    scraping_status[company_name][url]["status"] = result
                    time_taken = (datetime.now() - start_time).total_seconds()
                    scraping_status[company_name][url]["elapsed"] = time_taken
                    logger.error(
                        f"Scraping {url} for {company_name} failed after {time_taken} seconds: {result}"
                    )
            else:
                scraping_status[company_name][url]["status"] = "Failed: No result"
                time_taken = (datetime.now() - start_time).total_seconds()
                scraping_status[company_name][url]["elapsed"] = time_taken
                logger.error(
                    f"Scraping {url} for {company_name} failed with no result after {time_taken} seconds"
                )
        except Exception as e:
            scraping_status[company_name][url]["status"] = f"Failed: {str(e)}"
            time_taken = (datetime.now() - start_time).total_seconds()
            scraping_status[company_name][url]["elapsed"] = time_taken
            logger.error(f"Error in task for {url} for {company_name}: {e}")
        finally:
            if "elapsed" not in scraping_status[company_name][url]:
                time_taken = (datetime.now() - start_time).total_seconds()
                scraping_status[company_name][url]["elapsed"] = time_taken
                logger.info(
                    f"Task for {url} for {company_name} finished, time taken: {time_taken} seconds"
                )

    logger.info("Starting conversion of parsed report from markdown to PDF")
    input_dir = os.path.join("temp", "markdown")
    scraped_pdfs_to_upload = []
    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            input_path = os.path.join(input_dir, filename)
            pdf_path = convert_markdown_to_pdf(input_path)
            scraped_pdfs_to_upload.append(pdf_path)

    if len(scraped_pdfs_to_upload) != 0:
        logger.info(
            f"Conversion of report completed and uploaded to vector store with id {vector_store_id}"
        )
        upload_pdf_to_vector_store(ai, vector_store_id, scraped_pdfs_to_upload)
        logger.info(f"Removing Markdown file generated for {company_name}")
    else:
        logger.info(
            f"No PDF found from scrapped session, something went wrong.... Skipping upload"
        )

    for filename in os.listdir(input_dir):
        if filename.endswith(".md"):
            input_path = os.path.join(input_dir, filename)
            try:
                os.remove(input_path)
            except OSError:
                logger.info("File not found for deletion, skipping...")
                pass


def process_files(file_paths: list[str]) -> list[str]:
    """Process files and return converted PDF paths."""
    pdf_files = []
    for path in file_paths:
        filename = os.path.splitext(os.path.basename(path))[0] + ".pdf"
        pdf_path = os.path.join(converted_pdfs_folder, filename)
        if path.endswith(".pdf"):
            pdf_files.append(path)
        elif path.endswith(".docx"):
            convert_docx_to_pdf(path, pdf_path)
            pdf_files.append(pdf_path)
        elif path.endswith(".md"):
            convert_markdown_to_pdf_vs(path)
            pdf_files.append(pdf_path)
    return pdf_files


@app.post("/scrap")
async def scrap(
    response: Response,
    background_tasks: BackgroundTasks,
    company_name: str = Form(...),
    company_url: str = Form(...),
    instructions: Optional[str] = Form(""),
    persona: str = Form(...),
    customer_name: Optional[str] = Form(""),
    logo: UploadFile = File(None),
    timeout_seconds: Optional[int] = Form(60),
    additional_websites: Optional[str] = Form(None),
    attachments: list[UploadFile] = File(None),
):
    company_name = company_name.lower().strip().replace(" ", "_")
    if not validate_website(company_url):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"msg": "Provided URL is not valid"}

    logo_file = await fetch_or_upload_logo(company_name, logo)

    pdf_files = []

    if attachments:
        for attachment in attachments:
            attachment_path = os.path.join(attachments_folder, attachment.filename)
            with open(attachment_path, "wb") as f:
                f.write(attachment.file.read())
            pdf_files.append(attachment_path)

    if instructions:
        instructions = (
            f"You are a product support assistant for the company {company_name} and you answer questions based on the files provided. Keep the following in mind while answering as well"
            + instructions
        )
    else:
        instructions = f"You are a helpful product support assistant for the company {company_name} and you answer questions based on the files provided."

    try:
        db.collection("companies").get_first_list_item(f"company_name='{company_name}'")
        response.status_code = status.HTTP_409_CONFLICT
        logger.error(
            f"{company_name} has already been scrapped, skipping scraping for now"
        )
        return {"message": "This company has already been scraped"}
    except:
        pass

    logger.info(
        f"Creating vector store and assistant id for new company: {company_name}"
    )
    vector_store_id = create_vector_store(client=ai, company_name=company_name)
    assistant_id = create_assistant(
        client=ai,
        vector_store_id=vector_store_id,
        company_name=company_name,
        instructions=instructions,
    )

    logger.info("Converting attachments to PDF format")
    pdf_files = process_files(pdf_files)
    if len(pdf_files) != 0:
        logger.info(f"Uploading attachments to vector store to ID {vector_store_id}")
        upload_pdf_to_vector_store(ai, vector_store_id, pdf_files)
    else:
        logger.info("No attachments found! Skipping upload step")

    try:
        db.collection("companies").create(
            {
                "company_name": company_name,
                "company_url": company_url,
                "vector_store_id": vector_store_id,
                "assistant_id": assistant_id,
                "persona": persona,
                "customer_name": customer_name,
                "logo": logo_file,
                "additional_websites": additional_websites,
            }
        )

        websites_to_scrape = [company_url]
        if additional_websites:
            websites_to_scrape.extend(additional_websites.split(","))

        scraping_status[company_name] = {}

        for url in websites_to_scrape:
            scraping_status[company_name][url] = {
                "status": "Pending",
                "elapsed": 0,
            }

        logger.info("Starting Scraping task on background thread")
        background_tasks.add_task(
            run_scraping_task,
            company_name,
            websites_to_scrape,
            vector_store_id,
            timeout_seconds,
        )
        logger.info("Sending scraping begun response to client")

        response.status_code = status.HTTP_201_CREATED
        return {
            "message": "Company saved and scraping started",
            "company_name": company_name,
        }

    except ClientResponseError as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": f"Failed to save company {str(e)}"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"An unexpected error occurred: {str(e)}"}


@app.get("/scraping_status/{company_name}")
async def get_scraping_status(company_name: str):
    status = scraping_status.get(company_name)
    if status is None:
        return {"status": "Not Found", "company_name": company_name}

    response_data = {"total_scraped": total_scraped_companies, "companies": {}}

    overall_elapsed = 0
    all_completed = True

    for url, status_data in status.items():

        if status_data["status"] == "In Progress":
            status_data["elapsed"] = (
                datetime.now() - status_data["start_time"]
            ).total_seconds()
            all_completed = False

        response_data["companies"][url] = {
            "status": status_data["status"],
            "start_time": status_data["start_time"].isoformat(),
            "elapsed": status_data["elapsed"],
        }

        if "end_time" in status_data:
            response_data["companies"][url]["end_time"] = status_data[
                "end_time"
            ].isoformat()

        overall_elapsed += status_data["elapsed"]

    response_data["status"] = "Completed" if all_completed else "In Progress"
    response_data["overall_elapsed"] = overall_elapsed

    return response_data


@app.get("/companies/{company_name}")
async def get_company(company_name: str):
    try:
        companies = db.collection("companies").get_full_list()
        company = next((c for c in companies if c.company_name == company_name), None)
        if company:
            return company
        else:
            raise HTTPException(status_code=404, detail="Company not found.")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/companies")
async def get_all_companies():
    try:
        companies = db.collection("companies").get_full_list()
        return [company for company in companies]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/companies/{company_name}")
async def delete_company(company_name: str):
    try:
        companies = db.collection("companies").get_full_list()
        company = next((c for c in companies if c.company_name == company_name), None)

        if company:
            # Delete the assistant and vector store associated with the company
            delete_assistant_and_vs(ai, company.assistant_id, company.vector_store_id)

            # Now delete the company from the database
            db.collection("companies").delete(company.id)
            return {"detail": f"Company '{company_name}' successfully deleted."}
        else:
            raise HTTPException(status_code=404, detail="Company not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask")
async def ask_query(
    company_name: str = Body(...), persona: str = Body(...), prompt: str = Body(...)
):
    logger.info(
        f"\nQuestion : {prompt}\nCompany Name : {company_name}\nPersona : {persona}\n\n"
    )
    company_name = company_name.strip().lower().replace(" ", "_")
    key = f"{company_name}<SEP>{persona}"
    if key in session_manager:
        value = session_manager[key]
        assistant_id = value["assistant_id"]
        thread_id = value["thread_id"]
        vector_store_id = value["vector_store_id"]

    else:
        try:
            company = db.collection("companies").get_first_list_item(
                f"company_name='{company_name}'"
            )
            assistant_id = company.assistant_id
            vector_store_id = company.vector_store_id
            thread_id = ai.beta.threads.create().id
            session_manager[key] = {
                "assistant_id": assistant_id,
                "vector_store_id": vector_store_id,
                "thread_id": thread_id,
            }
        except Exception as e:
            return {"message": "Requested company not found!", "error": e}

    try:
        sentence_queue = Queue()
        buffer_dict = {"buffer": ""}

        ai.beta.threads.messages.create(
            thread_id=thread_id, role="user", content=prompt
        )

        assistant_reply_parts = []
        run = ai.beta.threads.runs.create(
            thread_id=thread_id, assistant_id=assistant_id, stream=True
        )

        for event in run:
            process_stream_event(
                event, assistant_reply_parts, sentence_queue, buffer_dict
            )

        assistant_reply = "".join(assistant_reply_parts)
        logger.info(f"Generated Answer: {assistant_reply}")
        return {"answer": assistant_reply}

    except Exception as e:
        return {"message": "Something went wrong while generating response", "error": e}


if __name__ == "__main__":
    uvicorn.run("index:app", port=8000, host="0.0.0.0")
