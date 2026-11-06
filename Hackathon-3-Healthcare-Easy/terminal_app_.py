from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.rule import Rule
from rich.text import Text

import arabic_reshaper
from bidi.algorithm import get_display


# ============================================================
# HEALTHCARE EASY
# Multilingual Healthcare Information Explainer
# ============================================================

console = Console()


# ============================================================
# Supported languages
# ============================================================

LANGUAGES = [
    "Dutch",
    "English",
    "Arabic",
    "Romanian",
    "Lithuanian"
]


# ============================================================
# Gemini client
# ============================================================

# The API key is NOT stored in this file.
# Gemini reads GEMINI_API_KEY from the environment.

client = genai.Client()


# ============================================================
# Structured Gemini response
# ============================================================

class HealthcareExplanation(BaseModel):

    simple_explanation: str = Field(
        description=(
            "A simple explanation of the original healthcare message. "
            "Do not add medical information that is not present in the original."
        )
    )

    actions: list[str] = Field(
        description=(
            "Only actions explicitly stated in the original healthcare message. "
            "Never invent, infer, or add a new medical action."
        )
    )

    important_information: list[str] = Field(
        description=(
            "Only important facts explicitly present in the original healthcare "
            "message, such as medicine names, dosages, dates, times, appointment "
            "details, warnings, or important medical facts. "
            "Do NOT repeat actions already listed in the actions field. "
            "Do NOT write generic words such as 'medicine' or 'medication' "
            "unless the original message contains a specific medicine name. "
            "Focus on concrete facts the user should notice."
        )
    )

    missing_or_unclear_information: list[str] = Field(
        description=(
            "Important information that is missing, vague, or unclear and "
            "could affect understanding or following the original message. "
            "Do not list information that is merely nice to know. "
            "Do not invent missing information."
        )
    )

    requested_language_explanation: str = Field(
        description=(
            "A natural, grammatically correct explanation of the original "
            "healthcare message in the user's requested target language. "
            "Keep all important medical information faithful to the original."
        )
    )

    safety_note: str = Field(
        description=(
            "A clear statement that Healthcare Easy only explains provided "
            "healthcare information and does not diagnose, prescribe medication, "
            "recommend treatment, or replace healthcare professionals."
        )
    )


# ============================================================
# Gemini system instructions
# ============================================================

SYSTEM_INSTRUCTIONS = """
You are Healthcare Easy, a multilingual healthcare information explainer.

Your ONLY job is to explain the healthcare information provided by the user.

The goal is:

TRANSLATE + EXPLAIN + SIMPLIFY

The original healthcare message is the source of truth.

============================================================
SAFETY RULES
============================================================

1. DO NOT diagnose diseases or medical conditions.
2. DO NOT prescribe medication.
3. DO NOT recommend treatment.
4. DO NOT give new medical instructions.
5. DO NOT invent medical information.
6. DO NOT guess information that is missing.
7. DO NOT change important medical information.

You must preserve exactly:
- medicine names
- dosages
- numbers
- dates
- times
- warnings
- appointment information
- instructions
- quantities

8. If the original message is unclear, say that it is unclear.
9. If important information is missing, identify the missing information.
10. If clarification is needed, say that the user should ask an appropriate
healthcare professional for clarification.

Do NOT provide the missing information yourself.

============================================================
ACTIONS
============================================================

For the "actions" field:

Only include actions explicitly stated in the original message.

Do NOT infer a new action.
Do NOT turn general information into a medical recommendation.

If there is no explicit action, return an empty list.

============================================================
IMPORTANT INFORMATION
============================================================

Include ONLY concrete and important FACTS explicitly present
in the original message.

Do NOT repeat actions.

If there are no concrete important facts, return an empty list.

============================================================
MISSING OR UNCLEAR INFORMATION
============================================================

Only identify information that is missing or unclear AND important
for understanding or following the original message.

Do NOT invent missing information.

============================================================
SIMPLE EXPLANATION
============================================================

Explain the original healthcare message using simple language.

Make it easier to understand.

DO NOT add medical advice.
DO NOT change the meaning.
DO NOT remove important numbers, dates, times, dosages,
medicine names, warnings, or instructions.

============================================================
TARGET LANGUAGE — ALL OUTPUT FIELDS
============================================================

The selected Target language controls ALL AI-GENERATED RESULT CONTENT.

Every user-facing text field in the structured response MUST be written in
the selected Target language:

- simple_explanation
- actions
- important_information
- missing_or_unclear_information
- requested_language_explanation
- safety_note

Do NOT write these fields in English unless English is the selected Target
language.

The section headings displayed by the terminal interface may remain in
English, but the CONTENT inside every result section must be in the selected
Target language.

For "requested_language_explanation":

Explain the ORIGINAL message in the user's requested target language.

The translation must be:
- natural
- grammatically correct
- easy to understand
- faithful to the original meaning

Do NOT translate word-for-word if that creates unnatural language.

Preserve:
- medicine names
- dosages
- numbers
- dates
- times
- warnings
- instructions

Do not invent information during translation.

If something is unclear in the original, keep it unclear.

============================================================
LANGUAGE QUALITY
============================================================

When the requested language is Arabic:
Use natural Modern Standard Arabic.
Do not translate Dutch or English sentence structures literally.

When the requested language is English:
Use clear, natural, simple English.
Avoid unnecessarily complicated medical terminology.

When the requested language is Dutch:
Use clear, natural Dutch.

When the requested language is Romanian:
Use natural, grammatically correct Romanian.

When the requested language is Lithuanian:
Use natural, grammatically correct Lithuanian.

============================================================
FINAL TRANSLATION CHECK
============================================================

Before returning the requested-language explanation, silently check:

1. Is the grammar natural?
2. Does it sound like a real native speaker?
3. Is the meaning identical to the original?
4. Were any medical facts changed?
5. Were any numbers changed?
6. Were any dates changed?
7. Were any times changed?
8. Were any medicine names changed?
9. Were any dosages changed?
10. Was any information invented?
11. Did an unclear part remain unclear?

============================================================
SAFETY NOTE
============================================================

The safety note must clearly explain:

Healthcare Easy is an information explainer.
It is NOT medical advice.
It does not diagnose diseases or medical conditions.
It does not prescribe medication.
It does not recommend treatment.
It does not replace a doctor, nurse, pharmacist, interpreter,
or other healthcare professional.

============================================================
PRIVACY
============================================================

Do not request unnecessary personal information.

Do not ask the user to provide:
- national identification numbers
- passwords
- API keys
- unnecessary personal information

============================================================
FINAL RULE
============================================================

The original healthcare message is the source of truth.

If information is not in the original message:
DO NOT INVENT IT.

If information is unclear:
SAY THAT IT IS UNCLEAR.

If information is missing:
SAY THAT IT IS MISSING.

FINAL OUTPUT LANGUAGE CHECK:

Before returning the response, verify that every text field in the structured
schema is written in the selected Target language.

If Target language is Arabic, all six fields must be Arabic.
If Target language is Romanian, all six fields must be Romanian.
If Target language is Lithuanian, all six fields must be Lithuanian.
If Target language is Dutch, all six fields must be Dutch.
If Target language is English, all six fields must be English.

Return the result using the provided structured schema.
"""


# ============================================================
# Arabic terminal rendering
# ============================================================

def prepare_rtl_text(text, language):
    if language != "Arabic":
        return text

    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


# ============================================================
# Header
# ============================================================

def show_header():
    console.clear()

    console.print(
        Panel(
            "[bold white]🏥 HEALTHCARE EASY[/bold white]\n"
            "[dim]Understand your healthcare message[/dim]",
            title="[bold blue]AI for Good • SDG 10[/bold blue]",
            border_style="blue",
            padding=(1, 4)
        )
    )

    console.print()
    console.print(
        "[bold]Let's make your healthcare message easier to understand.[/bold]"
    )
    console.print("[dim]Translate • Explain • Simplify[/dim]")


# ============================================================
# Language selection
# ============================================================

def choose_language(title, question):
    console.print()

    language_panel = (
        f"[bold white]{question}[/bold white]\n\n"
        "[cyan]①[/cyan] Dutch       "
        "[cyan]②[/cyan] English       "
        "[cyan]③[/cyan] Arabic\n"
        "[cyan]④[/cyan] Romanian    "
        "[cyan]⑤[/cyan] Lithuanian"
    )

    console.print(
        Panel(
            language_panel,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
    )

    choice = Prompt.ask(
        "[bold]Your choice[/bold]",
        choices=["1", "2", "3", "4", "5"]
    )

    return LANGUAGES[int(choice) - 1]


# ============================================================
# Healthcare message input
# ============================================================

def get_healthcare_message():
    console.print()

    console.print(
        Panel(
            "[bold white]📝 Paste your healthcare message below.[/bold white]\n\n"
            "[dim]You can paste multiple lines.[/dim]\n"
            "[dim]When you are finished, press Enter on an empty line.[/dim]",
            title="[bold cyan]3. HEALTHCARE MESSAGE[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
    )

    lines = []

    while True:
        line = input()

        if line == "":
            break

        lines.append(line)

    message = "\n".join(lines).strip()

    if not message:
        console.print(
            "[bold red]Please enter a healthcare message.[/bold red]"
        )
        return get_healthcare_message()

    return message


# ============================================================
# Request preview
# ============================================================

def show_request_preview(source_language, target_language, message):
    console.print()

    preview = (
        f"[bold cyan]Message language[/bold cyan]      {source_language}\n"
        f"[bold cyan]Explanation language[/bold cyan]  {target_language}\n\n"
        f"[bold cyan]Message[/bold cyan]\n{message}"
    )

    console.print(
        Panel(
            preview,
            title="[bold]📋 YOUR REQUEST[/bold]",
            border_style="white",
            padding=(1, 2)
        )
    )


# ============================================================
# Gemini request
# ============================================================

def explain_healthcare(message, source_language, target_language):
    user_input = f"""
Source language:
{source_language}

Target language:
{target_language}

Healthcare message:

{message}
"""

    try:
        with console.status(
            "[bold cyan]🤖 Analyzing your healthcare message...[/bold cyan]",
            spinner="dots"
        ):
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=user_input,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_schema=HealthcareExplanation,
                    automatic_function_calling=(
                        types.AutomaticFunctionCallingConfig(
                            disable=True
                        )
                    )
                )
            )

        if not response:
            return None, "The AI did not return a response."

        result = response.parsed

        if not result:
            return None, "The AI returned an invalid structured response."

        return result, None

    except Exception as error:
        print()
        print(f"[dim]Technical error: {error}[/dim]")

        return None, (
            "The healthcare explanation could not be generated. "
            "Please check your internet connection and try again."
        )


# ============================================================
# Output quality guard
# ============================================================

def validate_and_clean_result(result, target_language):

    cleaned_important = []

    vague_items = {
        "medicine",
        "medication",
        "drug",
        "a medicine",
        "a medication",
        "healthcare",
        "healthcare information"
    }

    for item in result.important_information:
        item_clean = item.strip()

        if not item_clean:
            continue

        if item_clean.lower() in vague_items:
            continue

        cleaned_important.append(item_clean)

    result.important_information = cleaned_important

    unique_important = []

    for item in result.important_information:
        if item.lower() not in [
            existing.lower()
            for existing in unique_important
        ]:
            unique_important.append(item)

    result.important_information = unique_important

    result.actions = [
        item.strip()
        for item in result.actions
        if item.strip()
    ]

    result.missing_or_unclear_information = [
        item.strip()
        for item in result.missing_or_unclear_information
        if item.strip()
    ]

    return result


# ============================================================
# Display result
# ============================================================

def show_result(result, target_language):
    console.print()
    console.print(
        Rule(
            "[bold blue]HEALTHCARE EASY • RESULT[/bold blue]",
            style="blue"
        )
    )
    console.print()

    def display_text(value):
        return prepare_rtl_text(value, target_language)

    console.print(
        Panel(
            display_text(result.simple_explanation),
            title="[bold]🧠 SIMPLE EXPLANATION[/bold]",
            border_style="blue",
            padding=(1, 2)
        )
    )

    actions_text = Text()

    if result.actions:
        for action in result.actions:
            actions_text.append("• ", style="cyan")
            actions_text.append(display_text(action))
            actions_text.append("\n")
    else:
        actions_text.append(
            display_text("No specific action is clearly stated.")
        )

    console.print(
        Panel(
            actions_text,
            title="[bold]📌 WHAT DOES THE MESSAGE SAY I SHOULD DO?[/bold]",
            border_style="green",
            padding=(1, 2)
        )
    )

    important_text = Text()

    if result.important_information:
        for information in result.important_information:
            important_text.append("• ", style="yellow")
            important_text.append(display_text(information))
            important_text.append("\n")
    else:
        important_text.append(
            display_text("No specific important information identified.")
        )

    console.print(
        Panel(
            important_text,
            title="[bold]⚠️ IMPORTANT INFORMATION[/bold]",
            border_style="yellow",
            padding=(1, 2)
        )
    )

    unclear_text = Text()

    if result.missing_or_unclear_information:
        for information in result.missing_or_unclear_information:
            unclear_text.append("• ", style="magenta")
            unclear_text.append(display_text(information))
            unclear_text.append("\n")
    else:
        unclear_text.append(
            display_text(
                "No important missing or unclear information identified."
            )
        )

    console.print(
        Panel(
            unclear_text,
            title="[bold]❓ MISSING OR UNCLEAR INFORMATION[/bold]",
            border_style="magenta",
            padding=(1, 2)
        )
    )

    console.print(
        Panel(
            display_text(result.requested_language_explanation),
            title="[bold]🌍 EXPLANATION IN REQUESTED LANGUAGE[/bold]",
            border_style="cyan",
            padding=(1, 2)
        )
    )

    console.print(
        Panel(
            display_text(result.safety_note),
            title="[bold]⚕️ SAFETY NOTE[/bold]",
            border_style="red",
            padding=(1, 2)
        )
    )

    console.print()

    console.print(
        Panel(
            "[bold]Privacy reminder:[/bold]\n"
            "Do not enter unnecessary personal or sensitive information.",
            border_style="white",
            padding=(1, 2)
        )
    )


# ============================================================
# Main application
# ============================================================

def main():
    show_header()

    source_language = choose_language(
        "🌍  1. MESSAGE LANGUAGE",
        "What language is your healthcare message in?"
    )

    target_language = choose_language(
        "💬  2. EXPLANATION LANGUAGE",
        "Which language would you like to understand it in?"
    )

    message = get_healthcare_message()

    show_request_preview(
        source_language,
        target_language,
        message
    )

    console.print()

    ready = Confirm.ask(
        "[bold green]🚀 Ready to explain your healthcare message?[/bold green]",
        default=True
    )

    if not ready:
        console.print()
        console.print(
            Panel(
                "No problem. The request was cancelled.",
                title="[yellow]CANCELLED[/yellow]",
                border_style="yellow"
            )
        )
        return

    result, error_message = explain_healthcare(
        message,
        source_language,
        target_language
    )

    if error_message:
        console.print()
        console.print(
            Panel(
                error_message,
                title="[bold red]❌ ERROR[/bold red]",
                border_style="red",
                padding=(1, 2)
            )
        )
        return

    result = validate_and_clean_result(
        result,
        target_language
    )

    show_result(result, target_language)

    console.print()

    console.print(
        Rule(
            "[dim]End of Healthcare Easy[/dim]",
            style="dim"
        )
    )


if __name__ == "__main__":
    main()
