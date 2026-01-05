// ============================================================
// Smart Notes Summarizer - Main Script
// ============================================================

// -------------- Flash Message System ------------------------
const FLASH_MAX = 4;
const FLASH_DURATION = 5000;
const FLASH_DEDUP_MS = 1200;
let _flashHistory = {};

function showFlash(message, type = 'info') {
    try {
        const now = Date.now();
        if (_flashHistory[message] && now - _flashHistory[message] < FLASH_DEDUP_MS) {
            return;
        }
        _flashHistory[message] = now;

        let container = document.querySelector('.flash-messages');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-messages';
            container.style.position = 'fixed';
            container.style.top = '16px';
            container.style.right = '16px';
            container.style.zIndex = 2000;
            container.style.display = 'flex';
            container.style.flexDirection = 'column';
            container.style.gap = '10px';
            document.body.appendChild(container);
        }

        while (container.children.length >= FLASH_MAX) {
            container.removeChild(container.firstChild);
        }

        const flash = document.createElement('div');
        flash.className = `flash-message ${type}`;
        flash.textContent = message;
        flash.style.padding = '12px 16px';
        flash.style.borderRadius = '10px';
        flash.style.boxShadow = '0 6px 18px rgba(2,6,23,0.4)';
        flash.style.maxWidth = '340px';
        flash.style.fontWeight = '600';
        flash.style.opacity = '0';
        flash.style.transition = 'all 240ms ease-out';

        if (type === 'success') {
            flash.style.background = 'linear-gradient(90deg,#d1fae5,#bbf7d0)';
            flash.style.color = '#052e16';
        } else if (type === 'error') {
            flash.style.background = 'linear-gradient(90deg,#fecaca,#fca5a5)';
            flash.style.color = '#4b0b0b';
        } else if (type === 'warning') {
            flash.style.background = 'linear-gradient(90deg,#fef3c7,#fde68a)';
            flash.style.color = '#533f03';
        } else {
            flash.style.background = 'linear-gradient(90deg,#e6f2ff,#dbeafe)';
            flash.style.color = '#062244';
        }

        const closeBtn = document.createElement('button');
        closeBtn.textContent = '✕';
        closeBtn.style.marginLeft = '8px';
        closeBtn.style.background = 'transparent';
        closeBtn.style.border = 'none';
        closeBtn.style.cursor = 'pointer';
        closeBtn.style.fontSize = '14px';
        closeBtn.style.opacity = '0.8';
        closeBtn.onclick = () => fadeOutAndRemove(flash);
        flash.appendChild(closeBtn);

        container.appendChild(flash);
        requestAnimationFrame(() => { flash.style.opacity = '1'; });

        const timeout = setTimeout(() => fadeOutAndRemove(flash), FLASH_DURATION);

        setTimeout(() => delete _flashHistory[message], FLASH_DEDUP_MS + 200);

        function fadeOutAndRemove(el) {
            if (!el || el._fading) return;
            el._fading = true;
            el.style.transition = 'all 220ms ease-in';
            el.style.opacity = '0';
            setTimeout(() => {
                if (el.parentElement) el.parentElement.removeChild(el);
                clearTimeout(timeout);
            }, 240);
        }
    } catch (err) { console.error('Flash error:', err); }
}

// -------------- File Upload / Summarizer ---------------------
async function uploadFile() {
    const fileInput = document.getElementById("fileInput");
    const file = fileInput.files[0];
    if (!file) {
        showFlash("Please select a file to upload.", "warning");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    showFlash("Uploading file...", "info");

    try {
        const res = await fetch("/upload", { method: "POST", body: formData });
        const data = await res.json();

        if (data.error) {
            showFlash(data.error, "error");
            return;
        }

        const summaryBox = document.getElementById("summaryBox");
        summaryBox.value = data.summary;
        showFlash("Summary generated successfully!", "success");
    } catch (err) {
        showFlash("Upload failed.", "error");
        console.error(err);
    }
}

// -------------- Quiz Logic -----------------------
let currentQuiz = { questions: [], answeredQuestions: 0, score: 0 };

// Initialize quiz and button handlers
function initializeQuiz() {
    const generateQuizBtn = document.querySelector('.generate-quiz-btn');
    const copyBtn = document.querySelector('.copy-btn');
    const speakBtn = document.querySelector('.speak-btn');
    const saveBtn = document.querySelector('.save-btn');
    
    if (generateQuizBtn && !generateQuizBtn.dataset.bound) {
        generateQuizBtn.removeAttribute('onclick');
        generateQuizBtn.addEventListener('click', generateQuiz);
        generateQuizBtn.dataset.bound = 'true';
    }

    // Add copy functionality
    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            try {
                const summaryContent = document.querySelector('.summary-content pre')?.textContent;
                if (summaryContent) {
                    await navigator.clipboard.writeText(summaryContent);
                    showFlash('Summary copied to clipboard!', 'success');
                }
            } catch (err) {
                showFlash('Failed to copy summary', 'error');
            }
        });
    }

    // Add text-to-speech functionality with stop control
    if (speakBtn) {
        speakBtn.addEventListener('click', () => {
            const summaryContent = document.querySelector('.summary-content pre')?.textContent;
            const stopBtn = document.querySelector('.stop-btn');
            
            if (summaryContent && 'speechSynthesis' in window) {
                // Cancel any ongoing speech
                window.speechSynthesis.cancel();
                
                const utterance = new SpeechSynthesisUtterance(summaryContent);
                
                // Show stop button when speaking starts
                if (stopBtn) stopBtn.style.display = 'inline-flex';
                if (speakBtn) speakBtn.style.display = 'none';
                
                utterance.onend = () => {
                    // Hide stop button when speech ends naturally
                    if (stopBtn) stopBtn.style.display = 'none';
                    if (speakBtn) speakBtn.style.display = 'inline-flex';
                };
                
                window.speechSynthesis.speak(utterance);
                showFlash('Started reading summary', 'info');
            } else {
                showFlash('Text-to-speech not supported', 'warning');
            }
        });
    }
    
    // Add stop button functionality
    const stopBtn = document.querySelector('.stop-btn');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            const speakBtn = document.querySelector('.speak-btn');
            window.speechSynthesis.cancel();
            stopBtn.style.display = 'none';
            if (speakBtn) speakBtn.style.display = 'inline-flex';
            showFlash('Stopped reading summary', 'info');
        });
    }

    // Add save functionality
    if (saveBtn) {
        saveBtn.addEventListener('click', async () => {
            const summaryContent = document.querySelector('.summary-content pre')?.textContent;
            if (!summaryContent) {
                showFlash('No summary to save', 'warning');
                return;
            }

            try {
                const response = await fetch('/save-summary', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        content: summaryContent,
                        title: 'Summary ' + new Date().toLocaleDateString()
                    })
                });

                const data = await response.json();
                showFlash(data.message, data.success ? 'success' : 'error');
            } catch (err) {
                showFlash('Failed to save summary', 'error');
            }
        });
    }
}

// Reset quiz state
function resetQuizState() {
    currentQuiz = { questions: [], answeredQuestions: 0, score: 0 };
    const quizSection = document.getElementById('quizSection');
    const quizContainer = document.getElementById('quizContainer');
    const quizCompletion = document.getElementById('quizCompletion');
    
    if (quizSection) quizSection.style.display = 'none';
    if (quizContainer) quizContainer.innerHTML = '';
    if (quizCompletion) quizCompletion.style.display = 'none';
    
    updateQuizStats();
}

function generateNewQuiz() { generateQuiz(); }

async function generateQuiz() {
    // Try to use an on-page summary if available; otherwise ask server for a quiz
    const summaryEl = document.querySelector('.summary-content pre');
    const summary = summaryEl ? (summaryEl.textContent || '').trim() : '';

    const btn = document.querySelector('.generate-quiz-btn');
    const quizSection = document.getElementById('quizSection');
    const loadingSpinner = document.getElementById('loadingSpinner');

    if (btn) btn.disabled = true;
    if (loadingSpinner) loadingSpinner.style.display = 'flex';
    
    showFlash('Generating quiz questions...', 'info');

    try {
        const payload = summary ? { summary } : {};
        const res = await fetch('/generate-quiz', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        let data = null;
        try { 
            data = await res.json(); 
        } catch (e) { 
            throw new Error('Failed to parse server response');
        }

        if (!res.ok) {
            const msg = (data && data.error) ? data.error : 'Quiz generation failed on server.';
            throw new Error(msg);
        }

        // normalize possible shapes: { questions: [...] } or { quiz: [...] } or raw array
        const questions = (data && (data.questions || data.quiz)) 
            ? (data.questions || data.quiz) 
            : (Array.isArray(data) ? data : []);

        if (!questions || questions.length === 0) {
            showFlash('Please generate a summary first.', 'warning');
            return;
        }

        // Reset and update quiz state
        currentQuiz = { 
            questions: questions.map(q => ({ ...q, answered: false })), 
            answeredQuestions: 0, 
            score: 0 
        };

        // Display quiz section
        if (quizSection) {
            quizSection.style.display = 'block';
            document.getElementById('quizContainer').style.display = 'block';
            document.querySelector('.quiz-stats').style.display = 'block';
        }

        renderQuiz();
        updateQuizStats();
        showFlash('Quiz generated successfully!', 'success');
        
        // Scroll to quiz section
        quizSection?.scrollIntoView({ behavior: 'smooth' });
        
    } catch (err) {
        console.error('Quiz generation error:', err);
        showFlash(err.message || 'Failed to generate quiz. Please try again.', 'error');
    } finally {
        if (btn) btn.disabled = false;
        if (loadingSpinner) loadingSpinner.style.display = 'none';
    }
}

function renderQuiz() {
    const quizContainer = document.getElementById('quizContainer');
    if (!quizContainer) return;
    quizContainer.innerHTML = '';

    if (!currentQuiz.questions || currentQuiz.questions.length === 0) {
        showFlash('No quiz questions to display.', 'warning');
        return;
    }

    currentQuiz.questions.forEach((q, i) => {
        const div = document.createElement('div');
        div.className = 'quiz-question';
        div.innerHTML = `
            <div class="question-header">
                <span class="question-badge">Question ${i + 1}</span>
            </div>
            <p class="question-text">${q.question}</p>
            <div class="quiz-options">
                ${q.options.map((opt, idx) => `
                    <div class="quiz-option ${q.answered && idx === q.correctAnswer ? 'correct' : ''} 
                                         ${q.answered && idx === q.selectedAnswer && idx !== q.correctAnswer ? 'incorrect' : ''}"
                         onclick="selectAnswer(this, ${i}, ${idx})">
                        <span class="option-letter">${String.fromCharCode(65 + idx)}</span>
                        <span class="option-text">${opt}</span>
                    </div>
                `).join('')}
            </div>
            <div class="quiz-explanation" style="display: ${q.answered ? 'block' : 'none'}">
                <div class="explanation-header">
                    <i class="fas fa-info-circle"></i> Explanation
                </div>
                <div class="explanation-content">
                    <p>${q.explanation || 'No explanation available.'}</p>
                </div>
            </div>
        `;
        quizContainer.appendChild(div);
    });

    const completionDiv = document.createElement('div');
    completionDiv.className = 'quiz-completion';
    completionDiv.style.display = currentQuiz.answeredQuestions === currentQuiz.questions.length ? 'block' : 'none';
    completionDiv.innerHTML = `
        <div class="completion-card">
            <div class="completion-icon">🎉</div>
            <h2>Quiz Completed!</h2>
            <div class="score-display">
                You scored <span id="finalScore">0</span> out of <span id="totalScore">${currentQuiz.questions.length}</span>
            </div>
            <p id="scoreMessage" class="score-message"></p>
            <div class="completion-actions">
                <button class="btn btn-primary" onclick="generateNewQuiz()">
                    <i class="fas fa-redo"></i> Try Another Quiz
                </button>
                <button class="btn btn-outline" onclick="resetQuiz()">
                    <i class="fas fa-eye"></i> Review Answers
                </button>
            </div>
        </div>
    `;
    quizContainer.appendChild(completionDiv);
}

function selectAnswer(element, questionIndex, optionIndex) {
    const question = currentQuiz.questions[questionIndex];
    if (question.answered) return;

    const options = element.parentElement.getElementsByClassName('quiz-option');
    
    // Mark question as answered and store selected answer
    question.answered = true;
    question.selectedAnswer = optionIndex;
    currentQuiz.answeredQuestions++;
    
    // Show correct/incorrect
    Array.from(options).forEach((option, index) => {
        if (index === question.correctAnswer) {
            option.classList.add('correct');
        } else if (index === optionIndex && index !== question.correctAnswer) {
            option.classList.add('incorrect');
        }
        option.style.pointerEvents = 'none'; // Disable further clicks
    });

    // Update score if correct
    if (optionIndex === question.correctAnswer) {
        currentQuiz.score++;
        showFlash('Correct answer! 🎉', 'success');
    } else {
        showFlash('Not quite right. Try to remember the correct answer!', 'warning');
    }

    // Show explanation
    const explanation = element.parentElement.nextElementSibling;
    if (explanation) {
        explanation.style.display = 'block';
    }

    // Update quiz stats
    updateQuizStats();

    // Check if quiz is complete
    if (currentQuiz.answeredQuestions === currentQuiz.questions.length) {
        setTimeout(() => {
            showQuizCompletion();
        }, 1000);
    }
}

function showQuizCompletion() {
    const quizContainer = document.getElementById('quizContainer');
    const completionDiv = quizContainer?.querySelector('.quiz-completion');
    
    if (!completionDiv) return;
    
    const score = Math.round((currentQuiz.score / currentQuiz.questions.length) * 100);
    const finalScoreEl = document.getElementById('finalScore');
    const scoreMessageEl = document.getElementById('scoreMessage');
    
    if (finalScoreEl) {
        finalScoreEl.textContent = `${currentQuiz.score}`;
    }
    
    if (scoreMessageEl) {
        let message = '';
        if (score >= 90) {
            message = '� Outstanding! You\'ve mastered this content!';
        } else if (score >= 70) {
            message = '👏 Great job! You have a good understanding of the material.';
        } else if (score >= 50) {
            message = '📚 Good effort! Review the topics you missed to improve.';
        } else {
            message = '💪 Keep practicing! Review the material and try again.';
        }
        scoreMessageEl.textContent = message;
    }

    completionDiv.style.display = 'block';
    completionDiv.scrollIntoView({ behavior: 'smooth' });
    showFlash('Quiz completed! 🎉', 'success');
}


function updateQuizStats() {
    const total = currentQuiz.questions.length;
    const correct = currentQuiz.score;
    const percentage = Math.round((correct / total) * 100) || 0;

    const totalEl = document.getElementById('totalQuestions');
    const correctEl = document.getElementById('correctAnswers');
    const scoreEl = document.getElementById('scorePercentage');
    
    if (totalEl) totalEl.textContent = total;
    if (correctEl) correctEl.textContent = correct;
    if (scoreEl) scoreEl.textContent = `${percentage}%`;
}

function toggleAllAnswers() {
    currentQuiz.questions.forEach((question, index) => {
        const questionEl = document.querySelectorAll('.quiz-question')[index];
        if (!questionEl) return;

        const options = questionEl.getElementsByClassName('quiz-option');
        const explanation = questionEl.querySelector('.quiz-explanation');
        
        Array.from(options).forEach((option, idx) => {
            if (idx === question.correctAnswer) {
                option.classList.add('correct');
            }
        });
        
        if (explanation) {
            explanation.style.display = explanation.style.display === 'none' ? 'block' : 'none';
        }
    });
}

// Handle drag and drop file upload
function setupFileUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    
    if (!uploadArea || !fileInput) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('drag-over');
        });
    });

    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        if (files.length > 0) {
            const file = files[0];
            if (file.size > 10 * 1024 * 1024) {
                showFlash('File size exceeds 10MB limit', 'error');
                return;
            }
            fileName.textContent = file.name;
            showFlash('File selected successfully', 'success');
        }
    }
}

// Initialize on page load
// Global function to stop speaking
function stopSpeaking() {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const stopBtn = document.querySelector('.stop-btn');
        const speakBtn = document.querySelector('.speak-btn');
        if (stopBtn) stopBtn.style.display = 'none';
        if (speakBtn) speakBtn.style.display = 'inline-flex';
        showFlash('Stopped reading summary', 'info');
    }
}

// Add event listener to stop speech when navigating away
window.addEventListener('beforeunload', stopSpeaking);

document.addEventListener('DOMContentLoaded', () => {
    initializeQuiz();
    setupFileUpload();
});
