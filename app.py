from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
import PyPDF2
import random
import google.generativeai as genai
from dotenv import load_dotenv
import secrets
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Generate SECRET_KEY at runtime if not in environment
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print(f"🔑 Generated SECRET_KEY at runtime: {SECRET_KEY[:16]}...")

app.config['SECRET_KEY'] = SECRET_KEY
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['SUMMARIES_FOLDER'] = os.path.join(BASE_DIR, 'summaries')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini AI API configured successfully")
else:
    print("⚠️  GEMINI_API_KEY not found in environment variables. Using fallback mode.")

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SUMMARIES_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path, filename):
    """Extract text from different file types"""
    ext = filename.rsplit('.', 1)[1].lower()
    
    try:
        if ext == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif ext == 'pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                # Try to handle encrypted PDFs with no password
                if getattr(reader, 'is_encrypted', False):
                    try:
                        reader.decrypt('')
                    except Exception:
                        raise Exception("PDF appears to be encrypted and cannot be read without a password.")
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text() or ''
                    page_text = page_text.strip()
                    if page_text:
                        text_parts.append(page_text)
                return '\n\n'.join(text_parts)
        
        elif ext == 'docx':
            try:
                import docx
                document = docx.Document(file_path)
                paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
                return '\n'.join(paragraphs)
            except Exception:
                return extract_docx_simple(file_path, filename)
    
    except Exception as e:
        raise Exception(f"Error reading file: {str(e)}")

def extract_docx_simple(file_path, filename):
    """Simple DOCX text extraction without python-docx"""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        
        text = []
        
        with zipfile.ZipFile(file_path) as docx:
            with docx.open('word/document.xml') as document_file:
                tree = ET.parse(document_file)
                root = tree.getroot()
                
                # Define namespace
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                
                # Find all paragraph elements
                for paragraph in root.findall('.//w:p', ns):
                    paragraph_text = []
                    # Find all text elements in the paragraph
                    for text_elem in paragraph.findall('.//w:t', ns):
                        if text_elem.text:
                            paragraph_text.append(text_elem.text)
                    if paragraph_text:
                        text.append(''.join(paragraph_text))
        
        return '\n'.join(text) if text else ''
        
    except Exception as e:
        return ''

def get_gemini_model():
    """Get the correct Gemini model name"""
    try:
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception:
        try:
            return genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"Error getting Gemini model: {e}")
            return None

def clean_document_text(text):
    """Intelligently clean document text to extract meaningful content"""
    if not text:
        return ""
    
    # Remove common academic headers/footers
    header_patterns = [
        r'DEPARTMENT OF.*',
        r'SEMESTER.*',
        r'SUBJECT.*',
        r'ROLL NUMBER.*',
        r'STUDENT NAME.*',
        r'PROFESSOR.*',
        r'LABORATORY.*',
        r'EXPERIMENT.*',
        r'EXP\s*\d+.*',
        r'RESOURCES.*',
        r'APPARATUS.*',
        r'HARDWARE.*',
        r'SOFTWARE.*',
        r'CODE:.*',
        r'OUTPUT:.*',
        r'DATE:.*',
        r'PAGE\s*\d+',
        r'©.*',
        r'CONFIDENTIAL.*',
        r'UNIVERSITY OF.*',
        r'COLLEGE OF.*'
    ]
    
    for pattern in header_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove excessive whitespace but preserve structure
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    # Split into lines and filter meaningful content
    lines = text.split('\n')
    meaningful_lines = []
    
    for line in lines:
        line = line.strip()
        # Keep lines that have actual content (not just headers/form fields)
        has_sentence_punct = bool(re.search(r'[\.;!?]', line))
        if (((len(line) > 15 and len(line.split()) > 3) or has_sentence_punct) and
            not re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line) and  # Names
            not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', line) and  # Dates
            not re.match(r'^\w+@\w+\.\w+$', line)):  # Emails
            meaningful_lines.append(line)
    
    # If we have meaningful content, return it
    if meaningful_lines:
        return '\n'.join(meaningful_lines)
    
    # Fallback: try to extract sentences with actual content
    sentences = re.split(r'[.!?]+', text)
    meaningful_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if (len(sentence) > 30 and 
            len(sentence.split()) > 5 and
            not sentence.isupper()):
            meaningful_sentences.append(sentence)
    
    if meaningful_sentences:
        return '. '.join(meaningful_sentences) + '.'
    
    # Last resort: return cleaned original
    return ' '.join(text.split())

def summarize_with_gemini(text):
    """Generate high-quality summary using Gemini AI with improved system prompt"""
    if not GEMINI_API_KEY:
        return summarize_text_fallback(text)
    
    try:
        # Enhanced system prompt for better summarization
        system_prompt = """You are an expert academic and technical content summarizer. Your task is to create comprehensive, well-structured summaries that capture the essence and key information from documents.

CRITICAL GUIDELINES FOR SUMMARIZATION:

1. CONTENT ANALYSIS:
   - Identify the main topic and purpose of the document
   - Extract key concepts, theories, methodologies, and findings
   - Distinguish between main arguments and supporting details
   - Preserve technical accuracy and domain-specific terminology

2. DOCUMENT TYPE HANDLING:
   - ACADEMIC PAPERS: Focus on research questions, methodology, results, conclusions
   - TECHNICAL DOCUMENTS: Highlight specifications, processes, architectures
   - CODE/ALGORITHMS: Explain purpose, functionality, inputs/outputs, key logic
   - REPORTS: Extract main findings, recommendations, evidence

3. CONTENT FILTERING:
   - IGNORE: Headers, footers, page numbers, author information, dates, course codes
   - IGNORE: Administrative details, formatting elements, repetitive content
   - FOCUS ON: Substantive content, arguments, data, technical details

4. SUMMARY STRUCTURE:
   - Start with a clear overview statement
   - Organize information hierarchically (main points → supporting details)
   - Use bullet points for key findings and important details
   - Include technical specifications where relevant
   - End with conclusions or implications

5. QUALITY REQUIREMENTS:
   - Maintain original meaning and technical accuracy
   - Use clear, concise, professional language
   - Ensure logical flow between ideas
   - Preserve important quantitative data and specifications
   - Adapt depth based on document complexity

OUTPUT FORMAT:

DOCUMENT OVERVIEW:
[1-2 sentence high-level description of what the document is about]

KEY FINDINGS/CONTENT:
• [Main point 1 with specific details]
• [Main point 2 with specific details]
• [Main point 3 with specific details]

TECHNICAL DETAILS/METHODOLOGY:
[Relevant technical specifications, methods used, or implementation details]

CONCLUSIONS/RESULTS:
[Main conclusions, results, or outcomes presented in the document]

IMPORTANT NOTES:
[Any critical limitations, assumptions, or additional context]

Remember: Your summary should enable someone to understand the core content without reading the entire document, while maintaining all crucial technical and conceptual information."""

        model = get_gemini_model()
        if not model:
            return summarize_text_fallback(text)
        
        # Clean the text
        clean_text = clean_document_text(text[:25000])  # Increased limit for better context
        
        if len(clean_text.split()) < 30:
            return "❌ Document is too short or doesn't contain enough meaningful content for summarization."
        
        print(f"📄 Cleaned text for AI summarization: {len(clean_text)} characters")
        
        full_prompt = f"{system_prompt}\n\nDOCUMENT CONTENT TO SUMMARIZE:\n{clean_text}"
        
        response = model.generate_content(full_prompt)
        response_text = response.text.strip()
        
        if response_text and len(response_text) > 150:
            # Add statistics
            original_words = len(clean_text.split())
            summary_words = len(response_text.split())
            reduction = int((1 - summary_words / original_words) * 100) if original_words > 0 else 0
            
            final_summary = f"{response_text}\n\n📊 SUMMARY STATISTICS:\n• Original content: {original_words} words\n• Summary: {summary_words} words\n• Content reduced by: {reduction}%\n• AI-Powered Summary: ✅ Enabled"
            return final_summary
        else:
            return summarize_text_fallback(text)
            
    except Exception as e:
        print(f"Gemini API error: {e}")
        return summarize_text_fallback(text)

def summarize_text_fallback(text):
    """Actually intelligent fallback summarization"""
    clean_text = clean_document_text(text)
    
    if len(clean_text.split()) < 20:
        return "❌ Document is too short or doesn't contain enough meaningful content for summarization."
    
    # Extract the most meaningful parts
    paragraphs = [p.strip() for p in clean_text.split('\n\n') if len(p.strip()) > 30]
    sentences = [s.strip() + '.' for s in re.split(r'(?<=[.!?])\s+', clean_text.replace('\n', ' ')) if len(s.strip()) > 20]
    
    # Use paragraphs if available, otherwise use sentences
    if paragraphs:
        content_blocks = paragraphs
    else:
        content_blocks = sentences
    
    if len(content_blocks) < 2:
        # Merge consecutive short lines into synthetic paragraphs
        lines = [l.strip() for l in clean_text.split('\n') if l.strip()]
        merged = []
        buf = []
        curr_len = 0
        for l in lines:
            buf.append(l)
            curr_len += len(l)
            if curr_len >= 300:
                merged.append(' '.join(buf))
                buf = []
                curr_len = 0
        if buf:
            merged.append(' '.join(buf))
        content_blocks = merged if merged else [clean_text]
    
    # Take the most substantial content blocks
    overview = content_blocks[0] if len(content_blocks) > 0 else ""
    key_points = content_blocks[1] if len(content_blocks) > 1 else overview
    main_content = content_blocks[2] if len(content_blocks) > 2 else key_points
    additional_info = content_blocks[3] if len(content_blocks) > 3 else main_content
    
    # Try to identify what type of content this is
    content_lower = clean_text.lower()
    if any(word in content_lower for word in ['code', 'program', 'function', 'class', 'import', 'public', 'private', 'def ', 'function ', 'algorithm']):
        doc_type = "CODE/PROGRAM"
        purpose = "This appears to be programming code or technical implementation."
    elif any(word in content_lower for word in ['study', 'research', 'analysis', 'results', 'methodology', 'hypothesis', 'experiment']):
        doc_type = "ACADEMIC/RESEARCH"
        purpose = "This appears to be academic or research content."
    elif any(word in content_lower for word in ['report', 'analysis', 'findings', 'recommendation', 'executive summary']):
        doc_type = "BUSINESS/REPORT"
        purpose = "This appears to be a business report or analysis."
    else:
        doc_type = "GENERAL DOCUMENT"
        purpose = "This document contains various information and content."
    
    # Calculate statistics
    original_words = len(clean_text.split())
    summary_content = f"{overview} {key_points} {main_content}"
    summary_words = len(summary_content.split())
    reduction = int((1 - summary_words / original_words) * 100) if original_words > 0 else 0
    
    summary = f"""📚 DOCUMENT SUMMARY

🔍 DOCUMENT TYPE: {doc_type}
🎯 PURPOSE: {purpose}

📖 DOCUMENT OVERVIEW:
{overview}

💡 KEY CONTENT:
{key_points}

🔧 MAIN DETAILS:
{main_content}

📊 STATISTICS:
• Original content: {original_words} words
• Summary: {summary_words} words  
• Content reduced by: {reduction}%

💡 Note: Using basic summarization. For enhanced AI summaries with better understanding and accuracy, add your Gemini API key to enable AI-powered summarization."""
    
    return summary

def generate_quiz_with_gemini(summary_text, original_content=""):
    """Generate specific, content-based quiz questions using AI"""
    if not GEMINI_API_KEY:
        return generate_quiz_fallback(summary_text, original_content)
    
    try:
        system_prompt = """You are an expert quiz creator. Create 5 specific, challenging multiple-choice questions based on the ACTUAL CONTENT provided.

CRITICAL REQUIREMENTS:
1. Questions MUST be specific to the exact content - about technologies, methods, concepts, or details mentioned
2. Make questions challenging and thought-provoking, not obvious
3. Focus on technical details, implementation specifics, or unique aspects of the content
4. All answer options must be plausible and related to the content domain
5. Correct answers must be verifiable from the content
6. Do NOT repeat or duplicate questions. Ensure diversity across concepts (purpose, methods, data, results, limitations, architecture, APIs, functions, parameters, etc.)
7. Return exactly 5 questions if the content allows; prefer fewer only if insufficient information exists.
8. OPTIONS MUST BE SOURCED FROM THE CONTENT: Prefer verbatim or near‑verbatim phrases/sentences from the content. Do not invent facts. At least 3 options per question should be direct excerpts.

CONTENT ANALYSIS:
- If it's CODE: Ask about specific functions, libraries, algorithms, or implementation details
- If it's ACADEMIC: Ask about theories, methodologies, findings, or concepts
- If it's TECHNICAL: Ask about specifications, processes, or technical details

QUESTION EXAMPLES:
- "Which specific Java class is used for random number generation in this code?"
- "What HTTP method does the form use for submitting guesses?"
- "What is the range of numbers generated by the random function?"
- "How does the code handle invalid user input?"
- "What specific error handling approach is implemented?"

FORMAT AS JSON:
[
  {
    "question": "Specific technical question about the content?",
    "options": ["Specific technical option A", "Specific technical option B", "Specific technical option C", "Specific technical option D"],
    "correctAnswer": 0,
    "explanation": "Detailed technical explanation referencing specific parts of the content"
  }
]

Return ONLY the JSON array."""

        model = get_gemini_model()
        if not model:
            return generate_quiz_fallback(summary_text, original_content)
        
        # Use both summary and original content for better context
        content_for_quiz = original_content if original_content else summary_text
        short_content = content_for_quiz[:4000]  # Limit length
        
        full_prompt = f"{system_prompt}\n\nCONTENT TO ANALYZE FOR QUIZ:\n{short_content}"
        
        response = model.generate_content(full_prompt)
        
        if response.text:
            cleaned_response = response.text.strip()
            
            # Extract JSON from response
            if '```json' in cleaned_response:
                cleaned_response = cleaned_response.split('```json')[1].split('```')[0].strip()
            elif '```' in cleaned_response:
                cleaned_response = cleaned_response.split('```')[1].split('```')[0].strip()
            
            try:
                quiz_data = json.loads(cleaned_response)
                
                if isinstance(quiz_data, dict):
                    quiz_data = quiz_data.get('questions') or quiz_data.get('data') or []
                
                if isinstance(quiz_data, list):
                    seen = set()
                    unique = []
                    for q in quiz_data:
                        if not isinstance(q, dict):
                            continue
                        if not all(k in q for k in ['question', 'options', 'correctAnswer', 'explanation']):
                            continue
                        key = (q['question'].strip().lower())
                        if key in seen:
                            continue
                        seen.add(key)
                        unique.append(q)
                    if unique:
                        print(f"✅ Generated {len(unique)} specific content-based quiz questions")
                        return unique[:5]
                raise ValueError("Invalid quiz format")
                    
            except Exception as e:
                print(f"JSON parsing error: {e}")
                return generate_quiz_fallback(summary_text, original_content)
                
        else:
            return generate_quiz_fallback(summary_text, original_content)
            
    except Exception as e:
        print(f"Gemini API error for quiz: {e}")
        return generate_quiz_fallback(summary_text, original_content)

def generate_quiz_fallback(summary_text, original_content=""):
    """Create specific quiz questions based on actual content analysis"""
    print("🔄 Using intelligent fallback quiz generation")
    
    content_to_analyze = original_content if original_content else summary_text
    questions = []

    # Extract meaningful sentences for question generation
    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content_to_analyze) if len(s.strip()) > 25]
    
    if len(raw_sentences) < 3:
        return [{
            "question": "The document content is insufficient to generate meaningful quiz questions.",
            "options": ["Upload a more substantial document", "Try a different file format", "Ensure the document has readable text", "Contact support"],
            "correctAnswer": 0,
            "explanation": "Please upload a document with more substantial content to generate quiz questions."
        }]

    # Generate comprehension questions from distinct sentences
    for i, sentence in enumerate(raw_sentences[:8]):  # Use first 8 sentences max
        if len(questions) >= 5:
            break
            
        # Create variations of questions
        first_few_words = ' '.join(sentence.split()[:5])
        
        # Build options from other sentences
        other_sentences = [s for s in raw_sentences if s != sentence]
        random.shuffle(other_sentences)
        distractors = other_sentences[:3]
        
        # Ensure we have enough options
        while len(distractors) < 3:
            distractors.append("This information is not present in the document")
        
        options = [sentence] + distractors[:3]
        random.shuffle(options)
        correct_idx = options.index(sentence) if sentence in options else 0
        
        question_variations = [
            f"Which of the following statements is directly supported by the document?",
            f"According to the document, which statement is accurate?",
            f"Which information is explicitly stated in the content?",
            f"Based on the document, which claim is verified?"
        ]
        
        q = {
            "question": random.choice(question_variations),
            "options": options,
            "correctAnswer": correct_idx,
            "explanation": f"The correct answer is directly extracted from the document content. The other options may be unrelated or not supported by the text."
        }
        questions.append(q)

    # Deduplicate questions
    seen_questions = set()
    unique_questions = []
    
    for q in questions:
        question_text = q["question"].strip().lower()
        if question_text not in seen_questions:
            seen_questions.add(question_text)
            unique_questions.append(q)

    print(f"✅ Intelligent fallback generated {len(unique_questions)} quiz questions")
    return unique_questions[:5]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/summarizer')
def summarizer():
    summary = session.get('last_summary', '')
    return render_template('summarizer.html', summary=summary)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            flash('❌ No file selected', 'error')
            return redirect(url_for('summarizer'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash('❌ No file selected', 'error')
            return redirect(url_for('summarizer'))
        
        if file and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            unique_prefix = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f"{unique_prefix}_{original_name}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            print(f"💾 Saved upload to: {file_path}")
            
            try:
                print(f"📁 Processing file: {filename}")
                
                # Extract text from file
                original_text = extract_text_from_file(file_path, filename)
                
                if len(original_text.strip()) < 50:
                    flash('⚠️ The file was uploaded but contains very little readable text. Summary and quiz quality may be limited (scanned PDFs may need OCR).', 'warning')
                
                print(f"📄 Original text extracted: {len(original_text)} characters")
                
                # Store original content in session for quiz generation
                session['original_content'] = original_text
                
                # Generate summary
                summary_text = summarize_with_gemini(original_text)
                
                # Store in session
                session['last_summary'] = summary_text
                session['last_filename'] = filename
                session['original_length'] = len(original_text.split())
                session['summary_length'] = len(summary_text.split())
                
                ai_mode = "AI-Powered" if GEMINI_API_KEY else "Basic"
                flash(f'✅ File successfully processed using {ai_mode} summarization!', 'success')
                return redirect(url_for('summarizer'))
                
            except Exception as e:
                print(f"❌ Error in file processing: {str(e)}")
                flash(f'❌ Error processing file: {str(e)}', 'error')
                return redirect(url_for('summarizer'))
        
        else:
            flash('❌ Invalid file type. Please upload PDF, DOCX, or TXT files.', 'error')
            return redirect(url_for('summarizer'))
    
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        flash(f'❌ Unexpected error: {str(e)}', 'error')
        return redirect(url_for('summarizer'))

@app.route('/generate-quiz', methods=['POST'])
def generate_quiz_route():
    try:
        summary_text = request.json.get('summary', '')
        
        # If no summary provided in request, try to get from session
        if not summary_text:
            summary_text = session.get('last_summary', '')
        
        # Get original content from session for better quiz generation
        original_content = session.get('original_content', '')
        
        # Validate summary exists and has content
        if not summary_text or len(summary_text.strip()) < 50:
            return jsonify({
                'error': '❌ No sufficient summary available. Please upload and summarize a document first, then generate quiz.'
            }), 400
        
        print("🎯 Generating specific content-based quiz questions...")
        print(f"📝 Summary length: {len(summary_text)} characters")
        print(f"📝 Original content available: {len(original_content)} characters")
        
        # Generate quiz based on BOTH summary and original content for better context
        quiz_questions = generate_quiz_with_gemini(summary_text, original_content)
        
        # Store quiz in session for the quiz page
        session['last_quiz'] = quiz_questions
        
        print(f"✅ Quiz generated with {len(quiz_questions)} specific content-based questions")
        return jsonify({'questions': quiz_questions})
    
    except Exception as e:
        print(f"❌ Error generating quiz: {e}")
        return jsonify({
            'error': '❌ Failed to generate quiz. Please ensure you have summarized a document first and try again.'
        }), 500

@app.route('/save-summary', methods=['POST'])
def save_summary():
    try:
        data = request.json
        summary_content = data.get('content', '')
        
        if not summary_content:
            return jsonify({'success': False, 'message': '❌ No summary content to save'}), 400
        
        summary_data = {
            'title': data.get('title', 'Untitled Summary'),
            'content': summary_content,
            'date': datetime.now().isoformat(),
            'original_length': session.get('original_length', 0),
            'summary_length': session.get('summary_length', 0),
            'filename': session.get('last_filename', ''),
            'ai_generated': bool(GEMINI_API_KEY)
        }
        
        filename = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = os.path.join(app.config['SUMMARIES_FOLDER'], filename)
        
        with open(file_path, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        return jsonify({'success': True, 'message': '✅ Summary saved successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ {str(e)}'}), 500

@app.route('/dashboard')
def dashboard():
    summaries = []
    try:
        for filename in os.listdir(app.config['SUMMARIES_FOLDER']):
            if filename.endswith('.json'):
                file_path = os.path.join(app.config['SUMMARIES_FOLDER'], filename)
                with open(file_path, 'r') as f:
                    summary_data = json.load(f)
                    # Ensure date is properly formatted and accessible
                    if 'date' not in summary_data:
                        # Add date from filename if missing
                        summary_data['date'] = datetime.now().isoformat()
                    summaries.append(summary_data)
        
        # Sort by date, handling both string and datetime objects
        summaries.sort(key=lambda x: x.get('date', ''), reverse=True)
        
    except Exception as e:
        print(f"Error loading summaries: {e}")
        flash('Error loading saved summaries', 'error')
    
    # Calculate statistics with safe defaults
    total_files = len(summaries)
    total_original_words = sum(s.get('original_length', 0) for s in summaries)
    total_summary_words = sum(s.get('summary_length', 0) for s in summaries)
    words_reduced = max(0, total_original_words - total_summary_words)
    time_saved = words_reduced // 200  # Assuming 200 words per minute reading speed
    
    stats = {
        'total_files': total_files,
        'words_reduced': words_reduced,
        'time_saved': time_saved,
        'ai_enabled': bool(GEMINI_API_KEY)
    }
    
    return render_template('dashboard.html', summaries=summaries[:5], stats=stats)
    
@app.route('/get-last-summary')
def get_last_summary():
    summary = session.get('last_summary', '')
    filename = session.get('last_filename', 'Unknown File')
    return jsonify({
        'summary': summary,
        'filename': filename,
        'has_summary': len(summary.strip()) > 50
    })

@app.route('/quiz')
def quiz():
    quiz_data = session.get('last_quiz')
    return render_template('quiz.html', quiz_data=quiz_data)

user_history = []
response_history = []

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()

        if not user_input:
            return jsonify({'response': "Please enter a valid message."}), 400

        user_history.append(user_input)

        model = get_gemini_model()
        if not model:
            return jsonify({'response': "AI model not configured. Please check your Gemini API key."}), 500

        # Construct AI prompt
        prompt = (
        "You are Smart Note Summarizer, an intelligent academic assistant that helps students summarize notes, explain complex topics, and generate revision questions. "
        "Your answers must be clear, concise, and study-oriented. "
        "When asked to summarize, focus on key points, structure, and learning value. "
        "When asked to explain, use easy language and examples. "
        "When asked for a quiz, generate 3–5 relevant conceptual questions.\n\n"
        f"Previous user questions: {user_history[-5:]}\n"
        f"Previous bot responses: {response_history[-5:]}\n\n"
        f"User: {user_input}\n"
        "Smart Note Summarizer:"
    )

        # Generate AI response
        response = model.generate_content(prompt)
        bot_response = response.text.strip() if response and response.text else "I'm here to help! Could you please clarify your question?"
        bot_response= bot_response.replace('StudyWise:', '').strip().replace('**', '').strip().replace('*', '').strip()
        response_history.append(bot_response)
        return jsonify({'response': bot_response})

    except Exception as e:
        print(f"Error in /chat: {e}")
        return jsonify({'response': "Internal Server Error. Please try again later."}), 500
@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot.html')



@app.route('/get-last-quiz')
def get_last_quiz():
    quiz_data = session.get('last_quiz')
    return jsonify({'quiz': quiz_data, 'has_quiz': quiz_data is not None})

@app.errorhandler(413)
def too_large(e):
    flash('❌ File too large. Please upload files smaller than 10MB.', 'error')
    return redirect(url_for('summarizer'))

@app.errorhandler(500)
def internal_error(e):
    flash('❌ An internal error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)