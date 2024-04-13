import boto3
import json
import sys
import eda_assistant_model_options
from botocore.client import Config
from anthropic_bedrock import AnthropicBedrock


## -- Bedrock Config
bedrock_config = Config(connect_timeout=120, read_timeout=120, retries={'max_attempts': 0})
bedrock_client = boto3.client('bedrock-runtime')
bedrock_agent_client = boto3.client('bedrock-agent')
bedrock_agent_client_runtime = boto3.client("bedrock-agent-runtime", config=bedrock_config)
configured_region = boto3.Session().region_name
supported_regions = ['us-west-2', 'us-east-1']
endpoint_url_dict = {'us-west-2' : 'https://bedrock.us-west-2.amazonaws.com/', 
                     'us-east-1' : 'https://bedrock.us-east-1.amazonaws.com/' }

# Check if the configured region is supported for the Bedrock service
def check_bedrock_region():
    try:
        # Check if the configured region is available for the Bedrock service
        if configured_region in supported_regions:
            print(f"-I- The configured region ({configured_region}) is available for Amazon Bedrock.")
        else:
            print(f"-I- The configured region ({configured_region}) is not available for Amazon Bedrock. Please configure one of the available regions below: ")
            for region in supported_regions:
                print(f"-I- {region}")
            sys.exit(1)

    except bedrock_client.exceptions.ClientError as e:
        print(f"-E- Error: {e}")
        print("-E- Please check your AWS credentials and ensure you have the necessary permissions.")
        sys.exit(1)
    

# Queries a knowledge base and retrieves information from it.
def retrieve(query, kbId, numberOfResults=5):
    """Retrieves relevant data from knowledge base
    Args:
    query: Original User Query
    kbid: Knowledge Base ID

    Returns:
    Retrieve Response
    """
    return bedrock_agent_client_runtime.retrieve(
        retrievalQuery= {
            'text': query
        },
        knowledgeBaseId=kbId,
        retrievalConfiguration= {
            'vectorSearchConfiguration': {
                'numberOfResults': numberOfResults,
                'overrideSearchType': "HYBRID", # optional
            }
        }
    )


# Queries a knowledge base and generates responses based on the retrieved results. 
# The response cites up to five sources but only selects the ones that are relevant to the query.
def retrieveAndGenerate(input, kbId, model_id):
    """Retrieves relevant data from knowledge base and Generate summarized response using LLM
    Args:
    input: Original User Query
    kbid: Knowledge Base ID
    modelID: LLM specific Model identifier

    Returns:
    RAG Response
    """
    model_arn = f'arn:aws:bedrock:{configured_region}::foundation-model/{model_id}'
    return bedrock_agent_client_runtime.retrieve_and_generate(
        input={
            'text': input
        },
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': kbId,
                'modelArn': model_arn,
                'retrievalConfiguration': {
                    'vectorSearchConfiguration': {
                        'overrideSearchType': 'HYBRID'
                    }
                }
            }
        }

    )
    

# Get response from Bedrock, return text output without metadata
def get_bedrock_response(query, modelID, temperature, topp, topk, maxtokens):
    prompt_payload = get_model_prompt_payload(query, modelID, temperature, topp, topk, maxtokens)

    #TODO: Add error handling incase it cant connect to endpoint
    response = bedrock_client.invoke_model(body=prompt_payload,
                            modelId=modelID,
                            accept='application/json',
                            contentType = 'application/json'   
                            )
    
    response_body = json.loads(response.get("body").read())    

    if modelID in eda_assistant_model_options.anthropic_models:
        output_text = response_body.get('content')[0]['text']
    elif modelID in eda_assistant_model_options.mistral_models:
        output_text = response_body.get('outputs')[0]['text']
    else:
        output_text = response_body.get('results')[0].get('outputText')

    return output_text


# List All Foundational Models available in your AWS account
def get_available_bedrock_models():
    """
    List all available bedrock models in your AWS account.
    Returns:
        A list of available bedrock models.
    """
    bedrock = boto3.client(service_name='bedrock',
                       region_name=configured_region,
                       endpoint_url=endpoint_url_dict[configured_region])
    return bedrock.list_foundation_models()


# Fetch context from the response
def get_contexts(retrievalResults):
    contexts = []
    for retrievedResult in retrievalResults: 
        contexts.append(retrievedResult['content']['text'])

    return contexts


# Get specific instructions for llm
def get_system_prompt (modelID):
    system_prompt = "You are an expert in semiconductor chip design and electronic design automation. Your goal is to provide informative and substantive responses to assist in semiconductor design engineering. You are to respond in markdown format. If you dont know the exact answer, just say you don't know. Do not make up an answer"
    return system_prompt


#Procedures to generate appropriate prompt formats for specific models
def get_model_prompt_payload(prompt_body, modelID, temperature, top_p, top_k, max_tokens):
    """ Generate a dictionary of model kwargs for the language model.
    Args:
        modelID: LLM specific Model identifier
        temperature: Temperature for the model
        top_p: Top P for the model
        top_k: Top K for the model
        max_tokens: Max Tokens for the model
    Returns:
        A dictionary of model kwargs for the language model.
    """
    if modelID in eda_assistant_model_options.anthropic_models:
        messages = [{"role": "user", 
                     "content": prompt_body}]

        user_prompt_obj = json.dumps({
            "anthropic_version": "bedrock-2023-05-31", #must be this verion
            "temperature" : temperature, #only temperature override, no top_p or top_k (advanced mode for later)
            "max_tokens": max_tokens,
            "system": get_system_prompt(modelID),
            'messages': messages
        })

    elif modelID in eda_assistant_model_options.mistral_models:
        mistral_prompt = prompt_body
        user_prompt_obj = {"prompt": mistral_prompt,
                           "max_tokens": max_tokens,
                           "temperature": temperature
        }

    else: #default                                   
        user_prompt_obj = {"inputText": prompt_body,
                        "textGenerationConfig": {
                        "maxTokenCount": max_tokens,
                        "stopSequences": [],
                        "temperature":0,
                        "topP":1
                            },
                        }
    return user_prompt_obj

#Get Native Token Client
# For counting tokens. TODO: Make generic to model 
def get_token_client():
    return AnthropicBedrock()