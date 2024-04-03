## Import Python libraries and custom modules
import eda_assistant_model_options
import json
import boto3
import os
# from utils import opensearch, secret

##Bedrock and Bedrock Embeddings
from langchain_community.embeddings import BedrockEmbeddings
from langchain.llms.bedrock import Bedrock
from langchain_community.chat_models import BedrockChat

## Data Ingestion
from langchain.retrievers.bedrock import AmazonKnowledgeBasesRetriever
from langchain_community.document_loaders import DirectoryLoader

## Data splitting
from langchain_text_splitters import RecursiveCharacterTextSplitter

## Embeddings
from langchain_community.embeddings import BedrockEmbeddings

## Vector Stores
from langchain_community.vectorstores import FAISS
from langchain.indexes import VectorstoreIndexCreator
# from langchain_community.vectorstores import OpenSearchVectorSearch

## Chains
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

## LLM Models
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

#Bedrock Client
bedrock_client = boto3.client('bedrock-runtime')
region = 'us-west-2'


# Get specific instructions for llm
def get_langchain_system_prompt (modelID):
    """Generate a system prompt for the language model.
    
    Args:
    None

    Returns:
    A string to be used as the initial prompt for the language model.
    """

    system_prompt = "You are an expert in semiconductor chip design and electronic design automation. Your goal is to provide informative and substantive responses to assist in semiconductor design engineering. When asked for any code related tasks, just output the code, skip any explanation. You are to respond in markdown format. If you dont know the exact answer, just say you don't know. Do not make up an answer"
    return system_prompt


## Get model kwargs 
def get_langchain_model_kwargs(modelID, temperature = 0.1, topk = 1, max_tokens=10000):
    """Generate a dictionary of model kwargs for the language model.

    Args:
    Model ID, Temperature, Top K, Max Tokens

    Returns:
    A dictionary of model kwargs for the language model.
    """

    if modelID in eda_assistant_model_options.anthropic_models:
        model_kwargs = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system" : get_langchain_system_prompt(modelID),
                "top_k": topk,
                "top_p": 1,
        }
    elif modelID in eda_assistant_model_options.mistral_models:
        model_kwargs = {
            "temperature": temperature, #float
            "top_k": topk, #int
            "max_tokens": max_tokens #int
        }
    else: #default                                   
        model_kwargs = {
            "temperature": temperature,
            "top_k": topk,
            "max_tokens_to_sample": max_tokens
        }
    return model_kwargs


##Get Amazon Knowledge Bases Retriever
def get_langchain_kb_retriever(kb_id):
    """Generate a knowledge base retriever for the language model.

    Args:
    Knowledge Base ID

    Returns:
    A knowledge base retriever for the language model.
    """
    retriever = AmazonKnowledgeBasesRetriever(
            knowledge_base_id=kb_id,
            retrieval_config={"vectorSearchConfiguration": 
                            {"numberOfResults": 4,
                            'overrideSearchType': "HYBRID", # optional
                            }
                            },
        )
    return retriever


##Get Documents from File System:
def get_langchain_docs_fs(path):
    """Generate a list of documents from a file system path.

    Args:
    Path to the file system directory containing PDF documents.

    Returns:
    A list of documents from the file system directory.
    """
    loader = DirectoryLoader(path, use_multithreading=True, show_progress=True)
    docs = loader.load()
    print("-I- Total Files loaded: ", len(docs))
    print("-I- File paths loaded: ")
    doc_sources = [doc.metadata['source']  for doc in docs]
    for fd in doc_sources:
        print("-I- ", fd)
    return docs


## Split into chunks
def get_langchain_split_chunks(docs, chunksize):
    """Split a list of documents into chunks of a specified size.

    Args:
    docs: A list of documents.
    chunksize: The size of each chunk.

    Returns:
    A list of chunks of the specified size.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunksize, chunk_overlap=20, length_function=len
    )
    chunks = text_splitter.split_documents(docs)
    return chunks


## Create an Embeddings model
def create_langchain_vector_embedding_using_bedrock(bedrock_embedding_model_id):
    """Create a vector embedding model using the Bedrock Embeddings library.

    Args:
    bedrock_embedding_model_id: The ID of the embedding model to use.

    Returns:
    A vector embedding model using the Bedrock Embeddings library.
    """
    bedrock_embeddings_client = BedrockEmbeddings(
        client=bedrock_client,
        model_id=bedrock_embedding_model_id)
    return bedrock_embeddings_client


def format_documents(docs) -> str:
    """Concatenate page contents of multiple documents into a single string.

    Args:
        docs: A list of documents.

    Returns:
        A string containing the concatenated page contents of the documents.
    """
    return "\n\n".join(doc.page_content for doc in docs)

def create_rag_pipeline_with_sourcing(documents, prompt_template, llm) -> str:
    """Query documents using a parallel processing approach.

    Args:
        documents: A list of document objects.

    Returns:
        The answer to the query based on the documents content.
    """
    # Create a vector store from PDF documents
    # index_file_path = os.path.join(os.getcwd(), "faiss_index")
    vector_store = FAISS.from_documents(documents, create_langchain_vector_embedding_using_bedrock("amazon.titan-embed-text-v1"))
    retriever = vector_store.as_retriever()

    # Setup parallel processing chain for querying
    rag_chain_with_source = RunnableParallel(
        {"context": retriever, "question": RunnablePassthrough()}
    ).assign(
        answer=(
            RunnablePassthrough.assign(
                context=(lambda x: format_documents(x["context"]))
            )
            | prompt_template
            | llm
            | StrOutputParser()
        )
    )

    # Execute the query and return the response
    return rag_chain_with_source


## Setup a retrieval QA for documents
def get_langchain_doc_retrievalqa(modelID, vectorstore, docs, prompt_template, query):

    llm = BedrockChat(model_id=modelID, 
                    model_kwargs=get_langchain_model_kwargs(modelID),
                    client=bedrock_client)

    rag_pipeline_with_sourcing = create_rag_pipeline_with_sourcing(docs, prompt_template, llm)
    response = rag_pipeline_with_sourcing.invoke(query)
    return response


## Create a FAISS index, save index to a specified file path
def get_langchain_faiss_vector_store(documents, embeddings):
    """Create a vector store from a list of documents and embeddings.

    Args:
        documents: A list of document objects.
        embeddings: A list of embeddings corresponding to the documents.

    Returns:
        A vector store object.
    """
    index_file_path = os.path.join(os.getcwd(), "faiss_index")
    db = FAISS.from_documents(documents, embeddings)
    db.save_local(index_file_path)
    return db


# Get response from Langchain RAG, return text output without metadata
def get_langchain_retrievalqa(modelID, retriever, docs, prompt_template, query):
    """Create a retrieval chain for QA.
    
    Args:
        modelID : LLM model ID
        retriever: A retriever object
        prompt_template: A model specific prompt template
        query: original user query
        embeddings: A list of embeddings corresponding to the documents.

    Returns:
        Query Response 

    """
    llm = BedrockChat(model_id=modelID, 
                      model_kwargs=get_langchain_model_kwargs(modelID),
                      client=bedrock_client)

    #TODO: need to migrate to new chains
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": prompt_template}
    )

    return qa.invoke(query)


# Get model prompt template for langchain retrieval
def get_langchain_model_prompt(context, question, temperature, max_tokens, topp, topk, modelID):

    #Old prompt templating
    if modelID in eda_assistant_model_options.anthropic_models:
        #Claude Prompt Template
        PROMPT_TEMPLATE = """

        Human: You are an expert semiconductor chip design engineer with deep knowledge about electronic design automation tools and chip design flows. 
        Use the following pieces of context to provide a concise answer to the question at the end. If asked a code related task, just output the code.
        If you don't know the answer, just say that you don't know, don't try to make up an answer. 

        <context>
        {context}
        </context>
        
        Question: {question}

        Assistant:"""

        payload = json.dumps({
                "prompt": PROMPT_TEMPLATE,
                "temperature":0.5
            })

        final_prompt = PromptTemplate(
            template=PROMPT_TEMPLATE, 
            input_variables=["context", "question"]
        )

    #Mistral Prompt Template
    elif modelID in eda_assistant_model_options.mistral_models:

        # payload with model paramters
        payload = json.dumps({
            "prompt": question,
            "max_tokens":max_tokens,
            "temperature":temperature,
            "top_k": topk,
            "top_p":topp
        })


        final_prompt = PromptTemplate(
            template=PROMPT_TEMPLATE, 
            input_variables=["context", "question"]
        )

    return payload, final_prompt