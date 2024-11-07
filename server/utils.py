from openai import Client
from markdown_pdf import MarkdownPdf, Section
import os
import logging
import subprocess
import openai
from urllib.parse import urlparse, urlsplit, urljoin
from bs4 import BeautifulSoup
import httpx
from dotenv import load_dotenv
import re
import logging
from docx2pdf import convert
from icrawler.builtin import GoogleImageCrawler
from typing import Optional
from fastapi import UploadFile
from pocketbase.client import FileUpload

load_dotenv()

attachment_extensions = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"]

# Local Cache
markdown_files = []
attachment_files = []
scraping_status = dict()
session_manager = dict()


def create_logger():
    logs_folder = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_folder, exist_ok=True)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(process)d | %(message)s"
    )
    file_handler = logging.FileHandler(os.path.join(os.getcwd(), "logs", "session.log"))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


logger = create_logger()


async def fetch_or_upload_logo(
    company_name: str, logo: Optional[UploadFile]
) -> Optional[FileUpload]:
    """
    Handle logo retrieval. If logo is provided, upload it; otherwise, crawl Google Images.
    """
    google_crawler = GoogleImageCrawler(
        storage={"root_dir": os.path.join(os.getcwd(), "temp", "images")}
    )
    if logo:
        logo_binary = await logo.read()
        return FileUpload(logo.filename, logo_binary)

    logger.info(
        f"Attempting to retrieve logo for {company_name.replace('_', ' ')} from Google Images"
    )
    crawled_logo_path = None
    try:
        google_crawler.crawl(
            keyword=f"{company_name.replace('_', ' ')} Company Logo", max_num=1
        )

        images_dir = os.path.join(os.getcwd(), "temp", "images")
        crawled_files = os.listdir(images_dir)
        if crawled_files:
            crawled_logo_path = os.path.join(images_dir, crawled_files[0])
            logger.info(f"Logo saved at {crawled_logo_path}")
            with open(crawled_logo_path, "rb") as f:
                logo_binary = f.read()
            return FileUpload("logo.jpg", logo_binary)
        else:
            logger.warning("No images were saved by the crawler.")
            return None
    except Exception as e:
        logger.warning(
            f"Logo retrieval for {company_name.replace('_', ' ')} failed: {e}"
        )
        return None
    finally:
        if crawled_logo_path and os.path.exists(crawled_logo_path):
            logger.info("Removing crawled logo from images directory")
            os.remove(crawled_logo_path)


def create_vector_store(client: Client, company_name: str):
    """Create a vector store for company

    Args:
        client (Client): OpenAI Client
        company_name (str): Name of the company for which vector store will be generated (will be used to name the vector store)
    """
    vector_store = client.beta.vector_stores.create(name=company_name)
    logger.info(f"Vector ID generated for {company_name}")
    return vector_store.id


def create_assistant(
    client: Client, vector_store_id: str, company_name: str, instructions: str
):
    """Create assistant of a company using it's previously generated vector store and company name.

    Args:
        client (Client): OpenAI Client
        vector_store_id (str): Vector Store ID generated for the company
        company_name (str): Name of the company for which assistant needs to be generated

    Returns:
        str: Assistant ID of the generated assistant for company
    """
    assistant = client.beta.assistants.create(
        name=company_name,
        instructions=instructions,
        model="gpt-4o-mini",
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
    )
    logger.info(f"Assistant ID generated for {company_name}")
    return assistant.id


def delete_assistant_and_vs(client: Client, assistant_id: str, vector_store_id: str):
    """Delete the assistant and its corresponding vector store.

    Args:
        client (Client): OpenAI Client
        assistant_id (str): ID of the assistant to delete
        vector_store_id (str): ID of the vector store to delete

    Returns:
        dict: Confirmation message for deletion
    """
    try:
        # Delete the assistant
        client.beta.assistants.delete(assistant_id)
        logger.info(f"Assistant with ID {assistant_id} deleted.")

        # Delete the vector store
        client.beta.vector_stores.delete(vector_store_id)
        logger.info(f"Vector store with ID {vector_store_id} deleted.")

        return {"detail": "Assistant and vector store successfully deleted."}

    except Exception as e:
        logger.error(f"Error deleting assistant or vector store: {str(e)}")
        return {
            "detail": "Something went wrong when deleting vector store and assistant"
        }


def save_extensions(
    url: str, content: bytes, folder: str, extensions: list[str], company_name: str
):
    """Saves content to a file if the URL's extension is in the specified list.

    Args:
        url (str): The URL of the file.
        content (bytes): The content to save.
        folder (str): The folder where the file will be saved.
        extensions (list[str]): List of allowed file extensions.
        company_name (str): The company name for folder organization.

    Returns:
        None
    """

    folder_dir = os.path.join(os.getcwd(), folder, company_name)
    os.makedirs(folder_dir, exist_ok=True)

    file_extension = url.split(".")[-1].lower()
    if file_extension in extensions:
        file_name = url.split("/")[-1]
        file_path = os.path.join(folder_dir, file_name)

        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(file_name)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(folder_dir, f"{base_name}_{counter}{ext}")
                counter += 1

        with open(file_path, "wb") as file:
            file.write(content)

        attachment_files.append(file_path)
    logger.info(f"Saved the following attachements: {attachment_files}")


def generate_page_report(url: str, content: bytes, company_name: str):
    """Generates a Markdown report from webpage content.

    Args:
        url (str): The webpage URL.
        content (bytes): HTML content of the webpage.
        company_name (str): The company name for report organization.

    Returns:
        None
    """

    soup = BeautifulSoup(content, "lxml")
    title = (
        soup.title.string.strip()
        if soup.title and soup.title.string
        else "No Title Found"
    )
    description_meta = soup.find("meta", attrs={"name": "description"})
    description = (
        description_meta["content"].strip()
        if description_meta and description_meta.get("content")
        else "No Description Found"
    )
    body_text = "\n".join([p.get_text(strip=True) for p in soup.find_all("p")])

    report_content = f"""# {title}

##### URL: [{url}]({url})

**Description**: {description}

**Body Text**:

{body_text}

---

"""

    url_domain = urlsplit(url).netloc
    if not url_domain:
        return

    domain_name = (
        url_domain.split(".")[-2]
        if len(url_domain.split(".")) > 2
        else url_domain.split(".")[0]
    )
    reports_dir = os.path.join(os.getcwd(), "temp", "markdown")
    os.makedirs(reports_dir, exist_ok=True)

    report_filename_md = f"{domain_name}.md"
    report_filepath_md = os.path.join(reports_dir, report_filename_md)

    with open(
        report_filepath_md, "a", encoding="utf-8", errors="ignore"
    ) as report_file:
        report_file.write(report_content)

    if report_filepath_md not in markdown_files:
        markdown_files.append(report_filepath_md)

    logger.info(f"Markdown Report Generated for {url}")


def scrape_entire_website(
    start_url: str, company_name: str, max_pages: int = 1000
) -> None:
    """
    Scrapes a website starting from the given URL.

    Iteratively fetches pages and saves attachments if their URLs match specified extensions.
    Generates a report for HTML content found on the pages.

    Args:
        start_url (str): The starting URL for scraping.
        company_name (str): The name of the company for organizing reports.
        max_pages (int, optional): Maximum number of pages to scrape. Defaults to 250.
    """
    if not start_url:
        raise ValueError("Start URL cannot be empty")

    if not company_name:
        raise ValueError("Company name cannot be empty")

    if not isinstance(max_pages, int) or max_pages <= 0:
        raise ValueError("Max iterations must be a positive integer")

    base_domain = urlparse(start_url).netloc
    scraped_urls = set()
    urls_to_scrape = [start_url]

    while urls_to_scrape and len(scraped_urls) < max_pages:
        url = urls_to_scrape.pop(0)
        if not url:
            logger.warning(f"Skipping null URL")
            continue

        if url in scraped_urls:
            continue

        try:
            response = httpx.get(url, verify=False, timeout=5)
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPError) as e:
            logger.error(f"Got an error while scraping {start_url} : {e}")
            continue

        if not response:
            logger.warning(f"Skipping empty response for {url}")
            continue

        scraped_urls.add(url)

        content_type = response.headers.get("Content-Type", "").lower()
        if any(url.lower().endswith(f".{ext}") for ext in attachment_extensions):
            save_extensions(
                url,
                response.content,
                os.path.join(os.getcwd(), "temp", "attachments"),
                attachment_extensions,
                company_name,
            )
            continue

        if "text/html" not in content_type:
            logger.debug(f"Invalid page response: {content_type}, skipping this URL")
            continue
        else:
            generate_page_report(url, response.content, company_name)

        soup = BeautifulSoup(response.content, "lxml")
        new_urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            joined_url = urljoin(url, href)
            parsed_joined_url = urlparse(joined_url)

            if (
                parsed_joined_url.netloc == base_domain
                and joined_url not in scraped_urls
                and joined_url not in urls_to_scrape
            ):
                new_urls.add(joined_url)
        urls_to_scrape.extend(new_urls)


def convert_markdown_to_pdf(
    path: str, output_dir: str = os.path.join(os.getcwd(), "temp", "pdf")
):
    """
    Convert a Markdown file to PDF format with a Table of Contents and CSS styling.

    Args:
        path (str): Path to the Markdown file to be converted.
        output_dir (str): Directory where the generated PDF file will be saved.
                          Defaults to "temp/pdf".
    """

    pdf = MarkdownPdf(toc_level=2)

    with open(path, "r", encoding="utf-8") as file:
        content = file.read()

    pdf.add_section(Section(content))
    pdf.meta["author"] = "NotTheRightGuy"

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf"
    )

    pdf.save(output_path)
    logger.info(f"The markdown file at {path} got saved as pdf to {output_dir}")
    return output_path


def convert_attachments_to_pdf():
    """
    Convert various attachment files (DOC, DOCX, PPT, PPTX) to PDF format.

        This function processes a set of attachment file paths, converting supported
        file types to PDF using LibreOffice. If a file is already in PDF format,
        it logs this information. Unsupported file types are also logged.

        Args:
            None

        Returns:
            None
    """
    for file_path in set(attachment_files):
        try:
            file_extension = file_path.split(".")[-1].lower()
            pdf_file_path = file_path.rsplit(".", 1)[0] + ".pdf"

            if file_extension in ["doc", "docx", "pptx", "ppt"]:
                result = subprocess.run(
                    [
                        "libreoffice",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        os.path.dirname(file_path),
                        file_path,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                if result.returncode == 0:
                    logger.info(f"Converted {file_path} to PDF at {pdf_file_path}")
                else:
                    logger.error(
                        f"Failed to convert {file_path} to PDF. LibreOffice error: {result.stderr.decode()}"
                    )
            elif file_extension == "pdf":
                logger.info(f"Attachment {file_path} is already a PDF.")
            else:
                logger.warning(
                    f"Cannot convert {file_path} to PDF. Unsupported file type."
                )

        except Exception as e:
            logger.error(f"Error converting attachment {file_path} to PDF: {e}")


def scrap_website(company_url: str, company_name: str):
    """Recursively scrape the specified company URL and convert results.

    Args:
        company_url (str): The URL of the company to be scraped.
        company_name (str): The name of the company for reporting purposes.

    Returns:
        None
    """
    scrape_entire_website(company_url, company_name)

    logging.info("Scraping completed.")
    logging.info("All conversions completed.")


def validate_website(website: str) -> bool:
    """
    Validates if the given website URL is in a valid format.

    Args:
        website (str): Website URL that needs to be validated.

    Returns:
        bool: Whether the provided string is a valid URL or not.
    """
    return website.startswith(("http://", "https://")) and "." in website


def extract_sentences(text):
    """
    Extracts sentences from the given text, returning a list of individual
    sentences and any remaining text that doesn't end with a sentence-ending punctuation.

    Args:
        text (str): The input text to extract sentences from.

    Returns:
        tuple: A tuple containing:
            - list: A list of sentences ending with '.', '!', or '?'.
            - str: Remaining text that does not end with '.', '!', or '?'.
    """
    sentence_end_pattern = re.compile(r"([^.!?]*[.!?])", re.M)
    sentences = sentence_end_pattern.findall(text)
    buffer = sentence_end_pattern.sub("", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    buffer = buffer.strip()
    return sentences, buffer


def process_stream_event(event, assistant_reply_parts, sentence_queue, buffer_dict):
    """
    Processes an event from the OpenAI assistant stream, extracting and queuing
    sentences while handling any additional buffering and special characters.

    Args:
        event (openai.types.beta.assistant_stream_event.ThreadMessageDelta):
            The incoming event message to process, expected to contain text data.
        assistant_reply_parts (list): A list accumulating cleaned text parts
            from the assistant's replies.
        sentence_queue (Queue): A queue where processed and complete sentences are added.
        buffer_dict (dict): A dictionary holding the "buffer" key, where partially
            complete sentence fragments are stored until fully formed.

    """
    if isinstance(event, openai.types.beta.assistant_stream_event.ThreadMessageDelta):
        if isinstance(
            event.data.delta.content[0],
            openai.types.beta.threads.text_delta_block.TextDeltaBlock,
        ):
            new_content = event.data.delta.content[0].text.value
            cleaned_text = ""
            i = 0
            while i < len(new_content):
                if new_content[i] != "【":
                    cleaned_text += new_content[i]
                elif new_content[i] == "【":
                    i += 1
                    while i < len(new_content) and new_content[i] != "】":
                        i += 1
                i += 1

            if cleaned_text:
                assistant_reply_parts.append(cleaned_text)
                buffer_dict["buffer"] += cleaned_text
                sentences, buffer_dict["buffer"] = extract_sentences(
                    buffer_dict["buffer"]
                )
                for sentence in sentences:
                    sentence_queue.put(sentence)


def upload_pdf_to_vector_store(
    client: Client, vector_store_id: str, pdf_files: list[str]
):
    """
    Uploads a PDF file to a specified vector store.

    Args:
        client (Client): Client instance for interacting with the vector store service.
        vector_store_id (str): Unique identifier of the target vector store.
        pdf_files (list): List of pdf_files path.
    """
    file_streams = [open(pdf_path, "rb") for pdf_path in pdf_files]
    try:
        client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id, files=file_streams
        )

        logger.info(
            f"{pdf_files} got uploded to vector store with id {vector_store_id}"
        )
    except Exception as e:
        logger.error(f"Caught an exception while uploading pdf to vector store : {e}")
    finally:
        for stream in file_streams:
            stream.close()


def convert_docx_to_pdf(docx_path: str, pdf_path: str):
    """Convert DOCX to PDF."""
    convert(docx_path, pdf_path)


def convert_markdown_to_pdf_vs(path: str, output_dir: str = "converted_pdfs/"):
    """
    Convert a Markdown file to PDF format with a Table of Contents and CSS styling.

    Args:
        path (str): Path to the Markdown file to be converted.
        output_dir (str): Directory where the generated PDF file will be saved.
                          Defaults to "converted_pdfs/".
    """

    pdf = MarkdownPdf(toc_level=2)

    with open(path, "r", encoding="utf-8") as file:
        content = file.read()

    pdf.add_section(Section(content))
    pdf.meta["author"] = "NotTheRightGuy"

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir, os.path.splitext(os.path.basename(path))[0] + ".pdf"
    )

    pdf.save(output_path)


if __name__ == "__main__":
    scrap_website("http://www.example.com", "Example")
