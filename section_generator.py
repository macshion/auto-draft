from utils.prompts import generate_paper_prompts, generate_keywords_prompts, generate_experiments_prompts, generate_bg_summary_prompts
from utils.gpt_interaction import get_responses, extract_responses, extract_keywords, extract_json
from utils.figures import generate_random_figures
import time
import os
from utils.prompts import KEYWORDS_SYSTEM
from utils.gpt_interaction import get_gpt_responses
import json

#  three GPT-based content generator:
#       1. section_generation: used to generate main content of the paper
#       2. keywords_generation: used to generate a json output {key1: output1, key2: output2} for multiple purpose.
#       3. figure_generation: used to generate sample figures.
#  all generator should return the token usage.


def section_generation_bg(paper, section, save_to_path, model):
    """
    The main pipeline of generating a section.
        1. Generate prompts.
        2. Get responses from AI assistant.
        3. Extract the section text.
        4. Save the text to .tex file.
    :return usage
    """
    print(f"Generating {section}...")
    prompts = generate_bg_summary_prompts(paper, section)
    gpt_response, usage = get_responses(prompts, model)
    output = gpt_response # extract_responses(gpt_response)
    paper["body"][section] = output
    tex_file = os.path.join(save_to_path, f"{section}.tex")
    # tex_file = save_to_path + f"/{section}.tex"
    if section == "abstract":
        with open(tex_file, "w") as f:
            f.write(r"\begin{abstract}")
        with open(tex_file, "a") as f:
            f.write(output)
        with open(tex_file, "a") as f:
            f.write(r"\end{abstract}")
    else:
        with open(tex_file, "w") as f:
            f.write(f"\section{{{section.upper()}}}\n")
        with open(tex_file, "a") as f:
            f.write(output)
    time.sleep(5)
    print(f"{section} has been generated. Saved to {tex_file}.")
    return usage


def section_generation(paper, section, save_to_path, model):
    """
    The main pipeline of generating a section.
        1. Generate prompts.
        2. Get responses from AI assistant.
        3. Extract the section text.
        4. Save the text to .tex file.
    :return usage
    """
    print(f"Generating {section}...")
    prompts = generate_paper_prompts(paper, section)
    gpt_response, usage = get_responses(prompts, model)
    output = gpt_response # extract_responses(gpt_response)
    paper["body"][section] = output
    tex_file = os.path.join(save_to_path, f"{section}.tex")
    # tex_file = save_to_path + f"/{section}.tex"
    if section == "abstract":
        with open(tex_file, "w") as f:
            f.write(output)
    else:
        with open(tex_file, "w") as f:
            f.write(output)
    time.sleep(5)
    print(f"{section} has been generated. Saved to {tex_file}.")
    return usage

# def keywords_generation(input_dict,  model, max_kw_refs = 10):
#     title = input_dict.get("title")
#     description = input_dict.get("description", "")
#     if title is not None:
#         prompts = generate_keywords_prompts(title, description, max_kw_refs)
#         gpt_response, usage = get_responses(prompts, model)
#         keywords = extract_keywords(gpt_response)
#         return keywords, usage
#     else:
#         raise ValueError("`input_dict` must include the key 'title'.")

def keywords_generation(input_dict):
    title = input_dict.get("title")
    max_attempts = 10
    attempts_count = 0
    while attempts_count < max_attempts:
        try:
            keywords, usage= get_gpt_responses(KEYWORDS_SYSTEM.format(min_refs_num=1, max_refs_num=10), title,
                                     model="gpt-3.5-turbo", temperature=0.4)
            print(keywords)
            output = json.loads(keywords)
            return output.keys(), usage
        except json.decoder.JSONDecodeError:
            attempts_count += 1
            time.sleep(20)
    raise RuntimeError("Fail to generate keywords.")

def figures_generation(paper, save_to_path, model):
    prompts = generate_experiments_prompts(paper)
    gpt_response, usage = get_responses(prompts, model)
    list_of_methods = list(extract_json(gpt_response))
    generate_random_figures(list_of_methods, os.path.join(save_to_path, "comparison.png"))
    return usage