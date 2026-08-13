import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle

def create_canva_resume_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=25,
        leftMargin=25,
        topMargin=20,
        bottomMargin=20
    )
    
    styles = getSampleStyleSheet()
    
    name_style = ParagraphStyle(
        'CanvaName',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#000000'),
        alignment=1,
        spaceAfter=3
    )
    
    subtitle_style = ParagraphStyle(
        'CanvaSubtitle',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#111111'),
        alignment=1,
        spaceAfter=4
    )
    
    contact_style = ParagraphStyle(
        'CanvaContact',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333'),
        alignment=1,
        spaceAfter=8
    )
    
    section_title_style = ParagraphStyle(
        'CanvaSectionTitle',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#000000'),
        spaceBefore=8,
        spaceAfter=3
    )

    body_style = ParagraphStyle(
        'CanvaBody',
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor('#222222'),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'CanvaBullet',
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=colors.HexColor('#222222'),
        leftIndent=11,
        firstLineIndent=-7,
        spaceAfter=2.5
    )

    col_title_style = ParagraphStyle(
        'ColTitleStyle',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=colors.HexColor('#000000'),
        spaceAfter=2
    )

    col_item_style = ParagraphStyle(
        'ColItemStyle',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#222222'),
        leftIndent=9,
        firstLineIndent=-6,
        spaceAfter=2
    )

    story = []

    # Header
    story.append(Paragraph("JOYDEEP DAS", name_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#000000'), spaceAfter=2, spaceBefore=0))
    story.append(Paragraph("Enterprise AI Architecture &nbsp;|&nbsp; Agentic AI & Systems Engineer &nbsp;|&nbsp; Generative AI Engineer", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#000000'), spaceAfter=4, spaceBefore=2))
    story.append(Paragraph("+91-9591799319 &nbsp;|&nbsp; joydeep.das.1611@gmail.com &nbsp;|&nbsp; linkedin.com/in/joydeep1611 &nbsp;|&nbsp; github.com/Joydeep1697 &nbsp;|&nbsp; nyayalegalos.com", contact_style))

    # Summary
    story.append(Paragraph("AI Solutions Architect with 5+ years of experience designing and delivering AI-powered software solutions across Agentic AI, Generative AI, voice intelligence, and enterprise applications. Architect of Nyaya Legal OS, Trynah.com (NAH), and Vaani AI, featuring multi-agent orchestration, proprietary fine-tuned LLM integration (NoveLaw), hybrid vector RAG retrieval, real-time speech processing, and proactive compliance automation. Experienced in translating business requirements into production-ready AI solutions through solution architecture, AI-assisted software development, technical documentation, testing, deployment, and cross-functional collaboration.", body_style))

    # Technical Expertise Section Title
    story.append(Paragraph("TECHNICAL EXPERTISE", section_title_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#000000'), spaceAfter=4, spaceBefore=1))

    # Technical Expertise 2-column table
    left_skills = [
        Paragraph("Artificial Intelligence & Voice Systems", col_title_style),
        Paragraph("&bull; Agentic AI Systems & Multi-Agent Orchestration", col_item_style),
        Paragraph("&bull; Speech Intelligence (STT/TTS) & Voice Assistants", col_item_style),
        Paragraph("&bull; Large Language Models (LLMs) & Fine-Tuning", col_item_style),
        Paragraph("&bull; Agentic RAG, Corrective RAG & Knowledge Graphs", col_item_style),
        Spacer(1, 3),
        Paragraph("Architecture & Product Strategy", col_title_style),
        Paragraph("&bull; AI Solution Architecture & Workflow Design", col_item_style),
        Paragraph("&bull; Product Strategy & Distributed System Design", col_item_style),
        Paragraph("&bull; Technical Documentation & Architectural Standards", col_item_style)
    ]

    right_skills = [
        Paragraph("Software Engineering", col_title_style),
        Paragraph("&bull; Python, FastAPI & React (PWA)", col_item_style),
        Paragraph("&bull; SQLite, RESTful APIs & WebSockets Audio Streaming", col_item_style),
        Paragraph("&bull; Cloud Infrastructure & Git / GitHub", col_item_style),
        Spacer(1, 3),
        Paragraph("Tools & Platforms", col_title_style),
        Paragraph("&bull; Azure AI & OpenAI Platform", col_item_style),
        Paragraph("&bull; Claude (Anthropic Platform)", col_item_style),
        Paragraph("&bull; LangChain, LlamaIndex & Power BI", col_item_style)
    ]

    skills_table = Table([[left_skills, right_skills]], colWidths=[280, 280])
    skills_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0)
    ]))
    story.append(skills_table)

    # Professional Experience Section Title
    story.append(Paragraph("PROFESSIONAL EXPERIENCE", section_title_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#000000'), spaceAfter=4, spaceBefore=1))

    # Job 1
    job1_header = Table([[
        Paragraph("<b>AI Solutions Architect | Nyaya OS Consulting</b>", ParagraphStyle('J1', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5)),
        Paragraph("<font color='#000000'><b>2025 - Present</b></font>", ParagraphStyle('D1', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, alignment=2))
    ]], colWidths=[390, 170])
    job1_header.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    story.append(job1_header)
    story.append(Paragraph("&bull; Architected and developed Nyaya Legal OS, Trynah.com, and Vaani AI, enterprise AI platforms designed to streamline risk verification, voice intelligence, and legal research workflows using natural language interaction and autonomous multi-agent orchestration.", bullet_style))
    story.append(Paragraph("&bull; Designed a modular architecture supporting agentic tool-calling protocols, multi-provider LLM routing (NVIDIA NIM, OpenAI, Claude, Gemini), speech processing, document intelligence, authentication, licensing, and intelligent automation.", bullet_style))
    story.append(Paragraph("&bull; Led the end-to-end product lifecycle including solution architecture, feature planning, AI-assisted software development, testing, documentation, branding, website development, and production deployment.", bullet_style))
    story.append(Paragraph("&bull; Established architectural standards, technical documentation, and multi-agent engineering workflows to ensure product quality, safety, and maintainability.", bullet_style))
    story.append(Spacer(1, 4))

    # Job 2
    job2_header = Table([[
        Paragraph("<b>Technical Expert | Infocom Books (India) Pvt Ltd</b>", ParagraphStyle('J2', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5)),
        Paragraph("<font color='#000000'><b>Jun 2023 - May 2026</b></font>", ParagraphStyle('D2', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, alignment=2))
    ]], colWidths=[390, 170])
    job2_header.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    story.append(job2_header)
    story.append(Paragraph("&bull; Designed and documented Generative AI solutions using GPT-4o, including Agentic RAG-based question-answering systems for educational and enterprise applications.", bullet_style))
    story.append(Paragraph("&bull; Developed Corrective RAG, Agentic RAG, and Knowledge-Graph-assisted RAG architectures with autonomous self-correction loops, reducing hallucinations and improving entity-level reasoning and contextual precision.", bullet_style))
    story.append(Paragraph("&bull; Built Python-based analytics pipelines and Power BI dashboards, delivering automated insights and production-grade technical documentation for AI and ML workflows.", bullet_style))
    story.append(Paragraph("&bull; Authored production-grade technical documentation covering AI architectures, multi-agent design patterns, ML workflows, and deployment guidelines.", bullet_style))
    story.append(Spacer(1, 4))

    # Job 3
    job3_header = Table([[
        Paragraph("<b>Intern - Machine Learning & Data Analytics | Pantech Solutions Pvt Ltd</b>", ParagraphStyle('J3', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5)),
        Paragraph("<font color='#000000'><b>Jan 2023 - Mar 2023</b></font>", ParagraphStyle('D3', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, alignment=2))
    ]], colWidths=[410, 150])
    job3_header.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    story.append(job3_header)
    story.append(Paragraph("&bull; Created Python scripts for data preprocessing, feature engineering, and visual analytics to support ML workflows.", bullet_style))
    story.append(Paragraph("&bull; Assisted in training, testing, and integrating machine learning models for classification and prediction tasks.", bullet_style))
    story.append(Paragraph("&bull; Performed exploratory data analysis (EDA) to identify patterns, anomalies, and insights across structured datasets.", bullet_style))
    story.append(Spacer(1, 4))

    # Job 4: Drone Design Engineer
    job4_header = Table([[
        Paragraph("<b>Drone Design Engineer | Jetwings Technologies</b>", ParagraphStyle('J4', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5)),
        Paragraph("<font color='#000000'><b>Jul 2019 - Oct 2021</b></font>", ParagraphStyle('D4', fontName='Helvetica-Bold', fontSize=9.5, leading=12.5, alignment=2))
    ]], colWidths=[390, 170])
    job4_header.setStyle(TableStyle([('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0)]))
    story.append(job4_header)
    story.append(Paragraph("&bull; Designed an agricultural drone equipped with spectral imaging technology to detect pest infestations and classify crops vs. weeds.", bullet_style))
    story.append(Paragraph("&bull; Performed ground and flight testing to validate design performance and imaging accuracy for agricultural use cases.", bullet_style))
    story.append(Paragraph("&bull; Documented engineering specifications, testing results, and system workflows for drone development projects.", bullet_style))
    story.append(Spacer(1, 6))

    # FEATURED PRODUCTS placed directly right after Drone Design Engineer
    story.append(Paragraph("FEATURED PRODUCTS", section_title_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#000000'), spaceAfter=6, spaceBefore=1))

    # Product 1: Nyaya Legal OS
    story.append(Paragraph("<b>1. NYAYA LEGAL OS - AI-Powered Legal Intelligence Operating System</b>", ParagraphStyle('P1Head', fontName='Helvetica-Bold', fontSize=9, leading=12)))
    story.append(Paragraph("Nyaya Legal OS is an enterprise-grade AI legal operating system engineered specifically for Indian statutory law and judicial research. It combines <b>NoveLaw</b> (a proprietary fine-tuned LLM) with a high-performance hybrid RAG engine (FAISS dense vector embeddings + SQLite FTS5 BM25 lexical search) over a 252+ document, 5,720-page legal corpus. The platform automates document ingestion, 36-category classification, entity extraction across 2,150+ judges and court sections, clause risk scoring (indemnity, liability, termination), citation knowledge graph mapping, and proactive statutory compliance gap analysis with sub-second retrieval.", body_style))
    story.append(Paragraph("&bull; <b>Hybrid Dense-Sparse RAG Engine:</b> Delivers sub-second retrieval across 3,150+ vector embeddings (768-dim all-mpnet-base-v2) combined with BM25 keyword matching.", bullet_style))
    story.append(Paragraph("&bull; <b>Automated Document Processing Pipeline:</b> Auto-extracts metadata, classifies documents into 36 legal categories, and resolves 2,150+ legal entities (courts, judges, sections, precedents).", bullet_style))
    story.append(Paragraph("&bull; <b>Clause Risk Scoring & Knowledge Graph:</b> Automatically identifies risky contractual clauses and builds dynamic cross-act citation graphs to detect legal contradictions.", bullet_style))
    story.append(Paragraph("&bull; <b>Proactive Compliance Matrix:</b> Tracks statutory limitation deadlines and alerts users to repealed or outdated acts.", bullet_style))
    story.append(Spacer(1, 6))

    # Product 2: Trynah.com
    story.append(Paragraph("<b>2. TRYNAH.COM (NAH) - AI-Powered Risk & Scam Verification Platform</b> &nbsp;|&nbsp; <font color='#2563EB'><u>https://trynah.com</u></font>", ParagraphStyle('P2Head', fontName='Helvetica-Bold', fontSize=9, leading=12)))
    story.append(Paragraph("Trynah.com (NAH) is an AI-powered decision verification and risk assessment platform designed to help users evaluate suspicious emails, messages, contracts, payment links, and offers before agreeing, paying, signing, or replying. Built as a full-stack Progressive Web App (PWA) with React, Python/FastAPI microservices, and Service Worker caching.", body_style))
    story.append(Paragraph("&bull; <b>AI Risk & Fraud Analysis Engine:</b> Developed NLP evaluation algorithms to detect deceptive language, financial risk signals, and scam patterns in user-submitted content.", bullet_style))
    story.append(Paragraph("&bull; <b>React Progressive Web App (PWA):</b> Engineered a responsive front-end PWA with Service Worker offline capabilities, dynamic state management, and optimized asset delivery.", bullet_style))
    story.append(Paragraph("&bull; <b>FastAPI Backend & Cloud Architecture:</b> Built asynchronous REST APIs for rapid risk scoring, low-latency prompt execution, and scalable production deployment.", bullet_style))
    story.append(Spacer(1, 6))

    # Product 3: Vaani AI
    story.append(Paragraph("<b>3. VAANI AI - Conversational Voice & Speech Intelligence Assistant</b>", ParagraphStyle('P3Head', fontName='Helvetica-Bold', fontSize=9, leading=12)))
    story.append(Paragraph("Vaani AI is an intelligent conversational voice assistant engineered for real-time speech-to-text (STT) transcription, natural language comprehension (NLU), automated voice command execution, and interactive multi-lingual audio intelligence.", body_style))
    story.append(Paragraph("&bull; <b>Speech Recognition & Audio Pipeline:</b> Built low-latency speech-to-text (STT) and text-to-speech (TTS) processing pipelines for real-time voice interaction.", bullet_style))
    story.append(Paragraph("&bull; <b>NLU & Intent Classification:</b> Integrated LLM intent classification and contextual dialogue synthesis for accurate voice command execution.", bullet_style))
    story.append(Paragraph("&bull; <b>WebSocket Audio Streaming:</b> Designed WebSocket streaming APIs to support real-time audio transmission and low-latency voice response generation.", bullet_style))
    story.append(Spacer(1, 6))

    # Education & Certifications Section Title
    story.append(Paragraph("EDUCATION & CERTIFICATIONS", section_title_style))
    story.append(HRFlowable(width="100%", thickness=1.2, color=colors.HexColor('#000000'), spaceAfter=4, spaceBefore=1))

    edu_left = [
        Paragraph("<b>EDUCATION</b>", col_title_style),
        Paragraph("Bachelor of Engineering (Aeronautical Engineering)", ParagraphStyle('E1', fontName='Helvetica', fontSize=8.5, leading=11.5)),
        Paragraph("<font color='#555555'>Acharya Institute of Technology (2019)</font>", ParagraphStyle('E2', fontName='Helvetica', fontSize=8.5, leading=11.5))
    ]

    cert_right = [
        Paragraph("<b>CERTIFICATIONS</b>", col_title_style),
        Paragraph("&bull; IBM Project Management Professional Certificate", col_item_style),
        Paragraph("&bull; Microsoft Certified: Azure AI Fundamentals (AI-900)", col_item_style)
    ]

    edu_table = Table([[edu_left, cert_right]], colWidths=[280, 280])
    edu_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0)
    ]))
    story.append(edu_table)

    doc.build(story)
    print("Canva PDF v11 generated successfully:", filename)

if __name__ == "__main__":
    out_file = r"C:\Users\joyde\Downloads\Joydeep_Das_Canva_Resume_v11.pdf"
    create_canva_resume_pdf(out_file)
