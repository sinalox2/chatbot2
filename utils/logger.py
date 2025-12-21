import os
from datetime import datetime

# ANSI escape codes for colors
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Logger:
    @staticmethod
    def _get_timestamp():
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def info(msg, tag="INFO"):
        print(f"{Colors.OKCYAN}[{Logger._get_timestamp()}] {Colors.BOLD}{tag}:{Colors.ENDC} {msg}")

    @staticmethod
    def success(msg, tag="OK"):
        print(f"{Colors.OKGREEN}[{Logger._get_timestamp()}] {Colors.BOLD}{tag}: ✅ {msg}{Colors.ENDC}")

    @staticmethod
    def warning(msg, tag="WARN"):
        print(f"{Colors.WARNING}[{Logger._get_timestamp()}] {Colors.BOLD}{tag}: ⚠️ {msg}{Colors.ENDC}")

    @staticmethod
    def error(msg, tag="ERR"):
        print(f"{Colors.FAIL}[{Logger._get_timestamp()}] {Colors.BOLD}{tag}: ❌ {msg}{Colors.ENDC}")

    @staticmethod
    def incoming(phone, msg):
        print(f"\n{Colors.OKBLUE}┌────────── INCOMING MESSAGE ──────────┐{Colors.ENDC}")
        print(f"{Colors.OKBLUE}│ {Colors.BOLD}FROM:{Colors.ENDC} {phone}")
        print(f"{Colors.OKBLUE}│ {Colors.BOLD}MSG:{Colors.ENDC}  {msg}")
        print(f"{Colors.OKBLUE}└──────────────────────────────────────┘{Colors.ENDC}")

    @staticmethod
    def rag_info(usa_rag, context_preview):
        status = f"{Colors.OKGREEN}✅ ACTIVO{Colors.ENDC}" if usa_rag else f"{Colors.FAIL}❌ INACTIVO{Colors.ENDC}"
        print(f"{Colors.OKCYAN}🔍 RAG:{Colors.ENDC} {status}")
        if usa_rag and context_preview:
            # Show a small preview of the context
            preview = context_preview[:100].replace('\n', ' ') + "..."
            print(f"   {Colors.OKCYAN}↳ Contexto:{Colors.ENDC} {preview}")

    @staticmethod
    def ai_response(respuesta, tokens=0, temp=0):
        print(f"{Colors.OKGREEN}🤖 AI:{Colors.ENDC} {respuesta[:150]}...")
        if tokens:
            print(f"   {Colors.OKCYAN}🎫 Tokens:{Colors.ENDC} {tokens} | {Colors.OKCYAN}🌡️ Temp:{Colors.ENDC} {temp}")
        print(f"{Colors.OKGREEN}──────────────────────────────────────{Colors.ENDC}\n")

    @staticmethod
    def startup(app_info):
        print(f"\n{Colors.HEADER}{Colors.BOLD}🚀 {app_info}{Colors.ENDC}")
        print(f"{Colors.HEADER}======================================{Colors.ENDC}")
