import gradio as gr
import os
import openai
from auto_backgrounds import generate_backgrounds, fake_generator
from auto_draft import generate_draft

openai_key = os.getenv("OPENAI_API_KEY")
access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
if access_key_id is None or secret_access_key is None:
    print("Access keys are not provided. Outputs cannot be saved to AWS Cloud Storage.\n")
    IS_CACHE_AVAILABLE = False
else:
    IS_CACHE_AVAILABLE = True

if openai_key is None:
    print("OPENAI_API_KEY is not found in environment variables. The output may not be generated.\n")
    IS_OPENAI_API_KEY_AVAILABLE = False
else:
    # todo: check if this key is available or not
    openai.api_key = openai_key
    try:
        openai.Model.list()
        IS_OPENAI_API_KEY_AVAILABLE = True
    except Exception as e:
        IS_OPENAI_API_KEY_AVAILABLE = False



def clear_inputs(text1, text2):
    return "", ""


def wrapped_generator(title, description, openai_key = None,
                      template = "ICLR2022",
                      cache_mode = IS_CACHE_AVAILABLE, generator=None):
    # if `cache_mode` is True, then follow the following steps:
    #        check if "title"+"description" have been generated before
    #        if so, download from the cloud storage, return it
    #        if not, generate the result.
    if generator is None:
        generator = generate_backgrounds
    if openai_key is not None:
        openai.api_key = openai_key
        openai.Model.list()

    if cache_mode:
        from utils.storage import list_all_files, hash_name, download_file, upload_file
        # check if "title"+"description" have been generated before
        file_name = hash_name(title, description) + ".zip"
        file_list = list_all_files()
        if file_name in file_list:
            # download from the cloud storage, return it
            download_file(file_name)
            return file_name
        else:
            # generate the result.
            # output = fake_generate_backgrounds(title, description, openai_key)
            output = generate_backgrounds(title, description,  template, "gpt-4")
            upload_file(file_name)
            return output
    else:
        # output = fake_generate_backgrounds(title, description, openai_key)
        output = generate_backgrounds(title, description,  template, "gpt-4")
        return output


theme = gr.themes.Monochrome(font=gr.themes.GoogleFont("Questrial")).set(
    background_fill_primary='#F6F6F6',
    button_primary_background_fill="#281A39",
    input_background_fill='#E5E4E2'
)

with gr.Blocks(theme=theme) as demo:
    gr.Markdown('''
    # Auto-Draft: 文献整理辅助工具-限量免费使用
    
    本Demo提供对[Auto-Draft](https://github.com/CCCBora/auto-draft)的auto_backgrounds功能的测试。通过输入一个领域的名称（比如Deep Reinforcement Learning)，即可自动对这个领域的相关文献进行归纳总结.    
    
    ***2023-04-30 Update***: 如果有更多想法和建议欢迎加入群里交流, 群号: ***249738228***.  
    
    ***2023-04-26 Update***: 我本月的余额用完了, 感谢乐乐老师帮忙宣传, 也感觉大家的体验和反馈! 我会按照大家的意见对功能进行改进. 下个月会把Space的访问权限限制在Huggingface的Organization里, 欢迎有兴趣的同学通过下面的链接加入! [AUTO-ACADEMIC](https://huggingface.co/organizations/auto-academic/share/HPjgazDSlkwLNCWKiAiZoYtXaJIatkWDYM) 
    
    ## 用法
    
    输入一个领域的名称（比如Deep Reinforcement Learning), 点击Submit, 等待大概十分钟, 下载output.zip，在Overleaf上编译浏览.  
    ''')
    with gr.Row():
        with gr.Column(scale=2):
            key =  gr.Textbox(value=openai_key, lines=1, max_lines=1, label="OpenAI Key", visible=not IS_OPENAI_API_KEY_AVAILABLE)
            # key =  gr.Textbox(value=openai_key, lines=1, max_lines=1, label="OpenAI Key", visible=False)
            title = gr.Textbox(value="Deep Reinforcement Learning", lines=1, max_lines=1, label="Title")
            description = gr.Textbox(lines=5, label="Description (Optional)")

            with gr.Row():
                clear_button = gr.Button("Clear")
                submit_button = gr.Button("Submit")
        with gr.Column(scale=1):
            style_mapping = {True: "color:white;background-color:green", False: "color:white;background-color:red"} #todo: to match website's style
            availability_mapping = {True: "AVAILABLE", False: "NOT AVAILABLE"}
            gr.Markdown(f'''## Huggingface Space Status  
             当`OpenAI API`显示AVAILABLE的时候这个Space可以直接使用.    
             当`OpenAI API`显示NOT AVAILABLE的时候这个Space可以通过在左侧输入OPENAI KEY来使用. 
            `OpenAI API`: <span style="{style_mapping[IS_OPENAI_API_KEY_AVAILABLE]}">{availability_mapping[IS_OPENAI_API_KEY_AVAILABLE]}</span>.  `Cache`: <span style="{style_mapping[IS_CACHE_AVAILABLE]}">{availability_mapping[IS_CACHE_AVAILABLE]}</span>.''')
            file_output = gr.File(label="Output")

    clear_button.click(fn=clear_inputs, inputs=[title, description], outputs=[title, description])
    submit_button.click(fn=wrapped_generator, inputs=[title, description, key], outputs=file_output)

demo.queue(concurrency_count=1, max_size=5, api_open=False)
demo.launch()
