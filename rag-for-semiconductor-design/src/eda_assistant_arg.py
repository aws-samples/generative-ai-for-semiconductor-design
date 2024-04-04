#All arguments

import argparse

parser = argparse.ArgumentParser(description='Semiconductor Design and Electronic Design Automation (EDA) Engineering Assistant')
parser.add_argument('--modelid', required=False, choices=['anthropic.claude-v2', 'anthropic.claude-instant-v1', 'anthropic.claude-3-sonnet-20240229-v1:0', 'anthropic.claude-3-haiku-20240307-v1:0'],  help='Provide foundation model ID')
parser.add_argument('--tokens', required=False, default=10000, help='Provide # of tokens')
parser.add_argument('--prompt', required=False, help='Provide prompt')
parser.add_argument('--kbid', required=False, help='Provide knowledge base id for RAG')
parser.add_argument('--temperature', required=False, default=0.1, help='Provide temperature for the model')
parser.add_argument('--top_p', required=False, default=0.5, help='Provide top_p for the model')
parser.add_argument('--top_k', required=False, default=50, help='Provide top_k for the model')
parser.add_argument('--norag', action="store_true", required=False, help='Use model as is')
parser.add_argument('--docchain', action="store_true", required=False, help='Provide a file path for RAG')
parser.add_argument('--filepath', type=str, required=False, help='Use model as is')
parser.add_argument('--webui', action="store_true", required=False, help='Use langchain implementation')
parser.add_argument('--show_all_models', required=False, action="store_true", help='display all models available to use')
parser.add_argument('--noref', action="store_true", required=False, help='Do not show references')
parser.add_argument('--endpoint_url', required=False, help='Provide region')
args = parser.parse_args()
