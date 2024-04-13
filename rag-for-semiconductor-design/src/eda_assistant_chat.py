
import sys
import json
import os
import platform
from weakref import ref
import pandas as pd
import streamlit as st

# Check major and minor version
if sys.version_info.major == 3 and sys.version_info.minor < 11:
    print("-E- This script requires Python 3.11 or higher!")
    sys.exit(1)
    

#Import eda_assistant modules
import eda_assistant_arg
import eda_assistant_bedrock_api
import eda_assistant_presigned_url
import eda_assistant_langchain_api


#TODO:
# Add error handling for aws configuration (boto3 error)


## -- Defaults
num_retrieve_results = 5
modelID= 'anthropic.claude-3-haiku-20240307-v1:0' if not eda_assistant_arg.args.modelid else eda_assistant_arg.args.modelid.strip()
default_prompt = "Write a verilog code to swap contents of two registers with and without a temporary register"
src_code_dir = os.path.dirname(os.path.abspath(__file__))
os_platform = platform.system()
supported_os_platforms_tokenclient = ["Linux", "Darwin"]
tokenclient = eda_assistant_bedrock_api.get_token_client()
user_prompt = ""

#Check if Bedrock Region is supported
check_region = eda_assistant_bedrock_api.check_bedrock_region()


## -- Streamlit code - GUI Mode
if eda_assistant_arg.args.webui: 
    st.set_page_config(page_title="EDA Engineering Assistant", page_icon=":trackball:", initial_sidebar_state="auto")
    st.header(":trackball: EDA Engineering Assistant")
    st.subheader("Ask questions pertaining to Digital Design, Analog design, EDA Software Tools")
    ref_urls = []
    
    # Sidebar User Settings
    model_temp = st.sidebar.slider(
        label='Model Temperature',
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.01,
        key='temperature'
    )   

    # Default Settings
    model_topp = eda_assistant_arg.args.top_p
    model_topk = eda_assistant_arg.args.top_k

    # Store the initial value of widgets in session state
    if "visibility" not in st.session_state:
        st.session_state.visibility = "visible"
        st.session_state.disabled = False

    #Initialize Session
    if 'temperature' not in st.session_state:
        st.session_state['temperature'] = eda_assistant_arg.args.temperature
    
    if 'kbid_input' not in st.session_state:
        st.session_state['kbid_input'] = ""

    # Create a single-select dropdown
    selected_option = st.sidebar.selectbox("Select a model:", ["anthropic.claude-3-haiku-20240307-v1:0", "anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-instant-v1", "anthropic.claude-v2"])
    st.write("You selected:", selected_option)

    # Create a model query approach: RAG or Base FM
    selected_option_rag = st.sidebar.selectbox("Select a model query approach:", ["RAG", "Base-FM"])
    st.write("You selected:", selected_option_rag)

    #Select Knowledge Base 
    kbid = st.sidebar.text_input(
        "Please enter Knowledge Base ID 👇",
        label_visibility=st.session_state.visibility,
        disabled=st.session_state.disabled,
        key= "kbid_input"
    )

    if st.session_state.kbid_input != "":
        print("-I- Selected KBID: ", kbid)
        st.write("Knowledge Base ID you provided:", kbid)

    # Accept user input through the text box
    if "Base-FM" in selected_option_rag and st.session_state.kbid_input == "":
        user_prompt = st.chat_input("Ask something...")
    elif "RAG" in selected_option_rag and st.session_state.kbid_input != "":
        user_prompt = st.chat_input("Ask something...")
    else:
        st.error('You must provide a Knowledge Base ID if you have selected RAG mode', icon="🚨")    

    #Sample Question List
    st.markdown("##### Sample Prompts: ")
    with open(os.path.join(src_code_dir, 'eda_assistant_sample_questions.json'), 'r', encoding="utf-8") as file:
        example_questions = json.load(file)
        question_list = [q for q in example_questions.values()]
    
    df = pd.DataFrame(question_list, columns=['Prompt'])

    # Display the DataFrame in Streamlit
    st.table(df)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "messages" not in st.session_state.keys():
        st.session_state.messages = [{"role": "assistant", "content": "How may I help you?"}]


    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


    if user_prompt:
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        # Display assistant response in chat message container
        with st.chat_message("user"):
            with st.spinner("Thinking..."):

                print("-I- GUI Prompt: ", user_prompt)
                if "RAG" in selected_option_rag:

                    print("-I- Model Temperature provided: ", model_temp)

                    retrieve_response = eda_assistant_bedrock_api.retrieve(user_prompt, kbid, 5)
                    retrievalResults = retrieve_response['retrievalResults']
                    retriever = eda_assistant_langchain_api.get_langchain_kb_retriever(kbid)
                    docs = retriever.get_relevant_documents(query=user_prompt)
                
                    context = eda_assistant_bedrock_api.get_contexts(retrievalResults)
                    model_payload, model_prompt = eda_assistant_langchain_api.get_langchain_model_prompt(context, user_prompt, model_temp, eda_assistant_arg.args.tokens, model_topp, model_topk, modelID)

                    retrieval_result = eda_assistant_langchain_api.get_langchain_retrievalqa(modelID, retriever, docs, model_prompt, user_prompt)
                    generated_text = retrieval_result['result']
                    citations = retrieval_result["source_documents"]


                    if len(retrieval_result["source_documents"]) > 0 and len(retrieval_result["source_documents"][0].metadata) > 0:
                        for x in range(len(retrieval_result["source_documents"][0].metadata)):
                            metadata_tag = retrieval_result["source_documents"][x].metadata
                            s3_uri = metadata_tag["location"]["s3Location"]["uri"]
                            temp_s3_url = eda_assistant_presigned_url.create_presigned_url(s3_uri)
                            ref_urls.append(temp_s3_url) 

                else:
                    print("-I- No RAG mode selected...")
                    generated_text = eda_assistant_bedrock_api.get_bedrock_response(user_prompt, modelID, model_temp, model_topp, model_topk, eda_assistant_arg.args.tokens)
                                             
                # TODO: Fix citations GUI output
                message_placeholder = st.empty()
                citation_placeholder = st.empty()
                message_placeholder.markdown(generated_text)

                if not eda_assistant_arg.args.noref:
                    if len(ref_urls) > 0:
                        unique_list = set(ref_urls)
                        ref_url_md = "\n".join(unique_list)
                        markdown_string = "###### References:\n\n"
                        for url in unique_list:
                            markdown_string += f"- {url}\n"
                        citation_placeholder.markdown(markdown_string)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": generated_text })


    
elif eda_assistant_arg.args.docchain:
    ## -- Experimental Feature - Need to fine-tune (pun intended)
    # 
    #   This capability is to allow RAG architectures using network file systems (NFS) as data sources.
    #   Does not work for very large file directories and storing chunks in vector db takes a long time. 
    #   This is just to demonstrate ability to source docs from file systems.
    #   Only works in CLI mode.
    #   TODO: test on FSX Netapp Ontap and FSX OpenZFS
    #   TODO: improve performance on the FAISS vector store creation. Do not create it if its already there.
    
    print("\n-I- Document Chain mode selected...")
    print("-I- ModelID selected: ", modelID)
    query = eda_assistant_arg.args.prompt if eda_assistant_arg.args.prompt else default_prompt


    print("-I- RAG mode selected...")
    if eda_assistant_arg.args.filepath is None:
        print("\n-E- Please provide a Knowledge Base ID to run in RAG mode")
        sys.exit(1)

    # Get raw docs
    print("-I- Getting raw documents from filepath...")
    if not os.path.exists(eda_assistant_arg.args.filepath):
        print("\n-E- Filepath does not exist, please ensure path is valida and user has permissions to access.")
        sys.exit(1)

    filedata = eda_assistant_langchain_api.get_langchain_docs_fs(eda_assistant_arg.args.filepath)
    
    # Split into chunks
    print("-I- Splitting documents into chunks...")
    chunksize = 1000
    documents = eda_assistant_langchain_api.get_langchain_split_chunks(filedata, chunksize)
 
    # Get embeddings
    print("-I- Creating embeddings model...")
    embeddings_modelid = 'amazon.titan-embed-text-v1'
    embeddings = eda_assistant_langchain_api.create_langchain_vector_embedding_using_bedrock(embeddings_modelid)

    # Get Vector Store
    print("-I- Creating & indexing vector store...")
    vectorstore = eda_assistant_langchain_api.get_langchain_faiss_vector_store(documents, embeddings)
    print("-I- FAISS Index Size - ", vectorstore.index.ntotal)

    # Retriever
    print("-I- Creating retriever...")
    retriever = vectorstore.as_retriever()

    #Generating Prompt Payload
    model_payload, model_prompt = eda_assistant_langchain_api.get_langchain_model_prompt(documents, query, eda_assistant_arg.args.temperature, eda_assistant_arg.args.tokens, eda_assistant_arg.args.top_p, eda_assistant_arg.args.top_k, modelID)

    # Get response
    print("-I- Getting response...")
    retrieval_result = eda_assistant_langchain_api.get_langchain_retrievalqa(modelID, retriever, documents, model_prompt, query)
    # retrieval_result_doc = eda_assistant_langchain_api.get_langchain_doc_retrievalqa(modelID, vectorstore, documents, model_prompt, query)
    response_body = retrieval_result['result']

    print("-I- Output Response...\n")
    print(response_body)


##CLI Mode
else:
    print("\n-I- CLI mode selected...")
    print("-I- ModelID selected: ", modelID)
    query = eda_assistant_arg.args.prompt if eda_assistant_arg.args.prompt else default_prompt    
    ref_urls = []

    print("-I- User Prompt: ", query) 

    if os_platform in supported_os_platforms_tokenclient:
        prompt_tokens = tokenclient.count_tokens(query)
        print("-I- No. of input prompt tokens:", prompt_tokens)
    
    if eda_assistant_arg.args.norag:
        response_body = eda_assistant_bedrock_api.get_bedrock_response(query, modelID, eda_assistant_arg.args.temperature, eda_assistant_arg.args.top_p, eda_assistant_arg.args.top_k, eda_assistant_arg.args.tokens)

    else:
        print("-I- RAG mode selected...")
        if eda_assistant_arg.args.kbid is None:
            print("\n-E- Please provide a Knowledge Base ID to run in RAG mode")
            sys.exit(1)
        else:
            kbid = eda_assistant_arg.args.kbid

        retrieve_response = eda_assistant_bedrock_api.retrieve(query, kbid, 5)
        retrievalResults = retrieve_response['retrievalResults']
        retriever = eda_assistant_langchain_api.get_langchain_kb_retriever(kbid)
        docs = retriever.get_relevant_documents(query=query)
        context = eda_assistant_bedrock_api.get_contexts(retrievalResults)
        model_payload, model_prompt = eda_assistant_langchain_api.get_langchain_model_prompt(context, query, eda_assistant_arg.args.temperature, eda_assistant_arg.args.tokens, eda_assistant_arg.args.top_p, eda_assistant_arg.args.top_k, modelID)
        retrieval_result = eda_assistant_langchain_api.get_langchain_retrievalqa(modelID, retriever, docs, model_prompt, query)
        response_body = retrieval_result['result']
        citations = retrieval_result["source_documents"]

        if len(retrieval_result["source_documents"]) > 0 and len(retrieval_result["source_documents"][0].metadata) > 0:
            for x in range(len(retrieval_result["source_documents"][0].metadata)):
                metadata_tag = retrieval_result["source_documents"][x].metadata
                s3_uri = metadata_tag["location"]["s3Location"]["uri"]
                temp_s3_url = eda_assistant_presigned_url.create_presigned_url(s3_uri)
                ref_urls.append(temp_s3_url)


    print("-I- Output Response...\n")
    print(response_body)

    if not eda_assistant_arg.args.noref:
            
        if len(ref_urls) > 0:
            print("\n-I- Reference URLs: ")
            for refurl in set(ref_urls):
                print("-I-", refurl)

    if os_platform in supported_os_platforms_tokenclient:
        print("\n-I- No. of output tokens: ", tokenclient.count_tokens(response_body)) 