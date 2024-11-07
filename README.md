# Conversational.AI

Conversational.AI is a React-based web application powered by FastAPI that allows users to create tailored chatbots for their companies. Users can upload their website URL and name through a form, and our project scrapes the website and any attached resources to craft a customized chatbot.

## Project Structure

The root directory contains three main folders:

- **client**: Contains the React frontend code.
- **pocketbase**: Includes configurations and data for Pocketbase, which serves as our storage and database solution.
- **server**: Contains the FastAPI backend code that handles the business logic and scraping functionalities.

## Features

- Upload a website URL and name.
- Automated scraping of website content and attachments.
- Creation of a tailored chatbot based on the scraped data.

## Prerequisites

Before you start, ensure you have the following installed:

- Node.js (for the React client)
- Python 3.x (for the FastAPI server)
- Pocketbase (provided as an executable)

## Getting Started

### 1. Setting Up the Client

Navigate to the `client` directory and install the necessary dependencies:

```bash
cd client
npm install
```

In `config.ts`, Add your backend endpoint and pocketbase endpoint, default values are already provided

```ts
export const HOST = "http://localhost:8000";
export const POCKETBASE = "http://localhost:8090";
```

To start the React development server, run:

```bash
npm run dev
```

### 2. Setting Up the Server

Navigate to the `server` directory and set up a virtual environment:

```bash
cd server
python -m venv .venv
source .venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

To start the FastAPI server, run:

```bash
python index.py
```

### 3. Running Pocketbase

In the `pocketbase` directory, run the provided Pocketbase executable:

```bash
./pocketbase serve # On Windows use pocketbase.exe serve
```

For Admin page navigate to `http://localhost:8090/_`
Admin Password will be

```bash
email : admin@email.com
password: password12345
```

### 4. Running Everything Together

After starting each component, ensure they are correctly connected:

- The React client should be running on [http://localhost:3000](http://localhost:3000).
- The FastAPI server should be accessible at [http://localhost:8000](http://localhost:8000).
- Pocketbase will run on its default port (e.g., [http://localhost:8090](http://localhost:8090)).

### 5. Logs

Once you start the server, logs will be available at logs/session.log

## Acknowledgements

- [React](https://reactjs.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pocketbase](https://pocketbase.io/)
