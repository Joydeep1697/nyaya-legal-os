import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

def create_resume_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        alignment=0,
        spaceAfter=2
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#2563EB'),
        alignment=0,
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'ContactStyle',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569'),
        alignment=0,
        spaceAfter=8
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=4
    )
    
    body_style = ParagraphStyle(
        'BodyStyle',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=4
    )
    
    bullet_style = ParagraphStyle(
        'BulletStyle',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155'),
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    job_title_style = ParagraphStyle(
        'JobTitleStyle',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=6,
        spaceAfter=2
    )

    story = []
    
    # Header
    story.append(Paragraph("JOYDEEP DAS", name_style))
    story.append(Paragraph("Enterprise AI Architecture | Agentic AI & Systems Engineer | Generative AI Engineer", subtitle_style))
    story.append(Paragraph("+91-9591799319 &nbsp;|&nbsp; joydeep.das.1611@gmail.com &nbsp;|&nbsp; linkedin.com/in/joydeep1611 &nbsp;|&nbsp; github.com/Joydeep1697 &nbsp;|&nbsp; novaosconsulting.com", contact_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=8, spaceBefore=0))
    
    # Summary
    story.append(Paragraph("PROFESSIONAL SUMMARY", section_heading))
    story.append(Paragraph("AI Solutions Architect with 5+ years of experience designing and delivering production-ready AI-powered software solutions across Agentic AI, Generative AI, intelligent automation, and enterprise applications. Architect of Nova AI, a modular Agentic AI productivity platform featuring autonomous workflow automation, multi-agent orchestration, document intelligence, and multi-LLM integration for scalable desktop AI experiences. Experienced in translating complex business requirements into high-performance AI architectures through agentic system design, AI-assisted software development, technical documentation, testing, deployment, and cross-functional leadership.", body_style))
    
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6, spaceBefore=6))

    # Technical Expertise
    story.append(Paragraph("TECHNICAL EXPERTISE", section_heading))
    story.append(Paragraph("<b>Agentic & Artificial Intelligence:</b> Agentic AI Systems, Multi-Agent Orchestration, Autonomous AI Agents, Tool-Calling Protocols, Large Language Models (LLMs), Agentic RAG & Corrective RAG, Prompt Engineering, Knowledge Graphs.", bullet_style))
    story.append(Paragraph("<b>Architecture & Product Strategy:</b> AI Solution Architecture, Agentic Workflow Design, Product Strategy, Distributed System Design, Technical Documentation & Standards.", bullet_style))
    story.append(Paragraph("<b>Software Engineering:</b> Python, FastAPI, SQLite, RESTful APIs, WebSockets, Git & GitHub.", bullet_style))
    story.append(Paragraph("<b>Tools, Frameworks & Platforms:</b> Azure AI, OpenAI Platform, Claude (Anthropic Platform), LangChain / LlamaIndex / Agentic Frameworks, Power BI.", bullet_style))
    
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6, spaceBefore=6))

    # Experience
    story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_heading))
    
    # Job 1
    story.append(Paragraph("AI Solutions Architect | Nova OS Consulting <font color='#64748B' size=8>(2025 - Present)</font>", job_title_style))
    story.append(Paragraph("&bull; Architected and developed Nova AI, an enterprise Agentic AI productivity platform engineered to streamline complex desktop workflows using natural language interaction and autonomous multi-agent orchestration.", bullet_style))
    story.append(Paragraph("&bull; Designed a modular architecture supporting agentic tool-calling protocols, multi-provider LLM routing (OpenAI, Claude, Gemini), document intelligence, licensing, and intelligent workflow automation.", bullet_style))
    story.append(Paragraph("&bull; Led the end-to-end product lifecycle including agentic system architecture, feature planning, AI-assisted software development, testing, documentation, branding, and production deployment.", bullet_style))
    story.append(Paragraph("&bull; Established architectural standards, multi-agent evaluation frameworks, and technical documentation to ensure system reliability, safety, and maintainability.", bullet_style))
    
    # Job 2
    story.append(Paragraph("Technical Expert | Infocom Books (India) Pvt Ltd <font color='#64748B' size=8>(Jun 2023 - Present)</font>", job_title_style))
    story.append(Paragraph("&bull; Designed and documented enterprise Generative AI solutions using GPT-4o, incorporating Agentic RAG-based question-answering systems for complex educational and legal/enterprise applications.", bullet_style))
    story.append(Paragraph("&bull; Developed Agentic RAG, Corrective RAG, and Knowledge-Graph-assisted RAG architectures featuring autonomous self-correction loops, reducing hallucinations and improving entity-level reasoning.", bullet_style))
    story.append(Paragraph("&bull; Built Python-based analytics pipelines and Power BI dashboards, delivering automated insights and production-grade technical documentation for AI/ML and agentic workflows.", bullet_style))
    story.append(Paragraph("&bull; Authored production-grade technical documentation covering AI architectures, multi-agent design patterns, ML workflows, and enterprise deployment guidelines.", bullet_style))
    
    # Job 3
    story.append(Paragraph("Intern - Machine Learning & Data Analytics | Pantech Solutions Pvt Ltd <font color='#64748B' size=8>(Jan 2023 - Mar 2023)</font>", job_title_style))
    story.append(Paragraph("&bull; Created Python scripts for data preprocessing, feature engineering, and visual analytics to support ML workflows.", bullet_style))
    story.append(Paragraph("&bull; Assisted in training, testing, and integrating machine learning models for classification and prediction tasks.", bullet_style))
    story.append(Paragraph("&bull; Performed exploratory data analysis (EDA) to identify patterns, anomalies, and insights across structured datasets.", bullet_style))

    # Job 4
    story.append(Paragraph("Drone Design Engineer | Jetwings Technologies <font color='#64748B' size=8>(Jul 2019 - Oct 2021)</font>", job_title_style))
    story.append(Paragraph("&bull; Designed an agricultural drone equipped with spectral imaging technology to detect pest infestations and classify crops vs. weeds.", bullet_style))
    story.append(Paragraph("&bull; Performed ground and flight testing to validate design performance and imaging accuracy for agricultural use cases.", bullet_style))
    story.append(Paragraph("&bull; Documented engineering specifications, testing results, and system workflows for hardware and sensor integration projects.", bullet_style))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6, spaceBefore=6))

    # Featured Product
    story.append(Paragraph("FEATURED PRODUCTS", section_heading))
    
    # Product 1: Nova Legal OS
    story.append(Paragraph("1. NOVA LEGAL OS - AI-Powered Legal Intelligence Operating System", job_title_style))
    story.append(Paragraph("Nova Legal OS is an enterprise AI operating system built for Indian law, integrating NoveLaw (a proprietary fine-tuned LLM) with a hybrid RAG engine (FAISS vector embeddings + SQLite FTS5 BM25 search) over a 252+ document, 5,720-page corpus.", body_style))
    story.append(Paragraph("&bull; Engineered a hybrid RAG retrieval pipeline delivering sub-second search citations across 3,150+ vector embeddings.", bullet_style))
    story.append(Paragraph("&bull; Developed automated document processing featuring 36-category classification, entity extraction (2,150+ courts, judges, sections), and clause risk scoring (indemnity, liability, termination).", bullet_style))
    story.append(Paragraph("&bull; Built a citation knowledge graph for auto-linking related precedents and proactive compliance gap analysis.", bullet_style))

    # Product 2: Nova AI
    story.append(Paragraph("2. NOVA AI - Agentic AI Productivity Platform", job_title_style))
    story.append(Paragraph("Nova AI is a modular, multi-agent AI productivity platform that streamlines desktop workflows through natural language interaction, autonomous agentic execution, document intelligence, and multi-LLM integration. Demonstrates end-to-end AI solution architecture, from agentic tool integration to secure authentication and deployment.", body_style))
    story.append(Paragraph("&bull; Autonomous Multi-Agent Task Orchestration & Desktop Workflow Automation", bullet_style))
    story.append(Paragraph("&bull; Agentic Document Intelligence, Clause Analysis & RAG Synthesis", bullet_style))
    story.append(Paragraph("&bull; Multi-LLM Integration (OpenAI, Gemini, Claude & Fine-Tuned Models)", bullet_style))
    story.append(Paragraph("&bull; Agentic Tool-Calling & Modular Plugin-Based Architecture", bullet_style))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6, spaceBefore=6))

    # Education & Certifications
    story.append(Paragraph("EDUCATION & CERTIFICATIONS", section_heading))
    story.append(Paragraph("&bull; Bachelor of Engineering (Aeronautical Engineering), Acharya Institute of Technology (2019)", bullet_style))
    story.append(Paragraph("&bull; IBM Project Management Professional Certificate", bullet_style))
    story.append(Paragraph("&bull; Microsoft Certified: Azure AI Fundamentals (AI-900)", bullet_style))

    doc.build(story)
    print("PDF generated successfully:", filename)

if __name__ == "__main__":
    out_file = r"C:\Users\joyde\Downloads\Joydeep_Das_Agentic_AI_Resume_v2.pdf"
    create_resume_pdf(out_file)
