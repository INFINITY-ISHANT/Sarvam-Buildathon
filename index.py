import gradio as gr
from fastapi import FastAPI

from app import demo

app = gr.mount_gradio_app(FastAPI(), demo, path="/")
