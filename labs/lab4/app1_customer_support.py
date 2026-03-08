import os
from typing import List, Dict, Any
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI
from langchain.agents import Tool, initialize_agent, AgentType

class CustomerSupportSystem:
    def __init__(self, knowledge_base_dir: str):
        self.kb_dir = knowledge_base_dir
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.vector_db = self._initialize_vector_db()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", 
            return_messages=True,
            output_key="answer"
        )
        
        # Initialize LLM (User should provide API key in env)
        self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        
        # Initialize Retriever Chain
        self.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vector_db.as_retriever(),
            memory=self.memory,
            return_source_documents=True
        )

    def _initialize_vector_db(self):
        """Load and vectorize documents from 3 distinct sources."""
        documents = []
        for filename in os.listdir(self.kb_dir):
            if filename.endswith(".txt"):
                loader = TextLoader(os.path.join(self.kb_dir, filename))
                documents.extend(loader.load())
        
        # Chunking Strategy
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(documents)
        
        return FAISS.from_documents(chunks, self.embeddings)

    def track_order(self, order_id: str) -> str:
        """Specialized tool 1: Track order status."""
        # Mock logic
        return f"Order {order_id} is currently: Out for Delivery."

    def check_availability(self, product_name: str) -> str:
        """Specialized tool 2: Check product stock."""
        # Mock logic
        return f"Product '{product_name}' is: In Stock."

    def get_support_agent(self):
        """Initialize Agent with tools."""
        tools = [
            Tool(
                name="OrderTracker",
                func=self.track_order,
                description="Use this when a user asks to track their order. Input is the Order ID."
            ),
            Tool(
                name="StockChecker",
                func=self.check_availability,
                description="Use this to check if a product is available in stock."
            )
        ]
        
        return initialize_agent(
            tools, 
            self.llm, 
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )

    def process_query(self, query: str):
        """Handle user queries with error handling."""
        try:
            # First try RAG for knowledge base questions
            response = self.qa_chain.invoke({"question": query})
            return {
                "status": "success",
                "answer": response["answer"],
                "sources": [doc.metadata['source'] for doc in response["source_documents"]]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"An error occurred: {str(e)}"
            }

if __name__ == "__main__":
    # Example Usage
    os.environ["OPENAI_API_KEY"] = "your-api-key-here"
    support = CustomerSupportSystem("./knowledge")
    result = support.process_query("What is the return policy for Product A?")
    print(result)
