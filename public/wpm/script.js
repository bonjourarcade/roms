class WPMTypingTest {
    constructor() {
        this.quotes = [];
        this.currentQuote = '';
        this.currentQuoteIndex = 0;
        this.currentBookTitle = '';
        this.currentBookLink = '';
        this.startTime = null;
        this.endTime = null;
        this.isTestActive = false;
        this.isTestComplete = false;
        this.timerInterval = null;
        this.totalCharacters = 0;
        this.correctCharacters = 0;
        this.typedCharacters = 0;
        this.testDuration = 60; // 60 seconds test
        this.timeRemaining = 60;

        this.initializeElements();
        this.loadQuotes();
        this.setupEventListeners();
    }

    initializeElements() {
        this.quoteTextElement = document.getElementById('quoteText');
        this.quoteSourceElement = document.getElementById('quoteSource');
        this.textInputElement = document.getElementById('textInput');
        this.wpmElement = document.getElementById('wpm');
        this.correctedWpmElement = document.getElementById('correctedWPM');
        this.timeLeftElement = document.getElementById('timeLeft');
        this.newQuoteButton = document.getElementById('newQuote');
        this.restartButton = document.getElementById('restart');
    }

    async loadQuotes() {
        try {
            console.log('Attempting to load quotes...');
            const response = await fetch('./quotes-20251018.json');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Quotes loaded successfully:', data);
            this.parseQuotes(data);
            this.displayRandomQuote();
            // Clear text box and auto-focus after quotes are loaded
            this.textInputElement.value = '';
            this.textInputElement.focus();
        } catch (error) {
            console.error('Error loading quotes:', error);
            this.quoteTextElement.innerHTML = `
                <div class="loading">
                    Erreur lors du chargement des citations.<br>
                    Détails: ${error.message}<br>
                    Veuillez vérifier que le fichier quotes-20251018.json existe.
                </div>
            `;
        }
    }

    parseQuotes(data) {
        // Extract all quotes from the JSON structure
        for (const bookTitle in data) {
            if (data[bookTitle].quotes && Array.isArray(data[bookTitle].quotes)) {
                for (const quoteObj of data[bookTitle].quotes) {
                    if (quoteObj.quote) {
                        // Clean up the quote text
                        let quote = quoteObj.quote.trim();
                        
                        // Remove star emojis
                        quote = quote.replace(/:\*:\s*/, '');
                        
                        // Only include quotes that are substantial (more than 20 characters)
                        if (quote.length > 20) {
                            this.quotes.push({
                                text: quote,
                                bookTitle: bookTitle,
                                bookLink: data[bookTitle].link
                            });
                        }
                    }
                }
            }
        }
        
        console.log(`Loaded ${this.quotes.length} quotes`);
    }

    displayRandomQuote() {
        if (this.quotes.length === 0) {
            this.quoteTextElement.innerHTML = '<div class="loading">Aucune citation disponible.</div>';
            return;
        }

        this.currentQuoteIndex = Math.floor(Math.random() * this.quotes.length);
        const quoteData = this.quotes[this.currentQuoteIndex];
        this.currentQuote = quoteData.text;
        this.currentBookTitle = quoteData.bookTitle;
        this.currentBookLink = quoteData.bookLink;
        
        this.renderQuoteWithProgress();
        this.updateBookSource();
        this.totalCharacters = this.currentQuote.length;
    }

    renderQuoteWithProgress() {
        let html = '';
        for (let i = 0; i < this.currentQuote.length; i++) {
            const char = this.currentQuote[i];
            let className = 'untyped';
            
            if (i < this.typedCharacters) {
                // Check if this character was typed correctly
                const inputValue = this.textInputElement.value;
                if (i < inputValue.length && inputValue[i] === char) {
                    className = 'correct';
                } else {
                    className = 'incorrect';
                }
            } else if (i === this.typedCharacters) {
                className = 'current';
            }
            
            // Handle special characters
            if (char === ' ') {
                html += `<span class="${className}">&nbsp;</span>`;
            } else if (char === '\n') {
                html += `<span class="${className}"><br></span>`;
            } else {
                html += `<span class="${className}">${char}</span>`;
            }
        }
        
        this.quoteTextElement.innerHTML = html;
    }

    setupEventListeners() {
        this.textInputElement.addEventListener('input', (e) => {
            this.handleInput(e.target.value);
        });

        this.textInputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
            }
        });

        this.newQuoteButton.addEventListener('click', () => {
            this.newQuote();
        });

        this.restartButton.addEventListener('click', () => {
            this.restartTest();
        });

        // Reset game on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.restartTest();
            }
        });
    }

    handleInput(inputValue) {
        // Auto-start test on first keystroke
        if (!this.isTestActive && inputValue.length > 0) {
            this.startTest();
        }

        if (!this.isTestActive) return;

        this.typedCharacters = inputValue.length;
        this.correctCharacters = 0;

        // Calculate correct characters for visual feedback
        for (let i = 0; i < Math.min(inputValue.length, this.currentQuote.length); i++) {
            if (inputValue[i] === this.currentQuote[i]) {
                this.correctCharacters++;
            }
        }

        this.updateStats();
        this.renderQuoteWithProgress();

        // Check if test is complete
        if (inputValue.length === this.currentQuote.length) {
            this.completeTest();
        }
    }

    startTest() {
        if (this.isTestActive) return;

        this.isTestActive = true;
        this.startTime = Date.now();
        this.timeRemaining = this.testDuration;
        this.textInputElement.disabled = false;
        this.textInputElement.focus();

        // Start timer
        this.timerInterval = setInterval(() => {
            this.updateTimer();
        }, 1000);
    }

    completeTest() {
        this.isTestComplete = true;
        this.endTime = Date.now();
        
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }

        this.textInputElement.disabled = true;
        
        // Calculate final stats before marking test as inactive
        const finalWPM = this.calculateWPM();
        const finalCorrectedWPM = this.calculateCorrectedWPM();
        
        // Show completion message
        setTimeout(() => {
            alert(`Test Terminé !\nMPM: ${finalWPM}\nMPM Corrigé: ${finalCorrectedWPM}`);
        }, 100);
        
        // Mark as inactive after calculations
        this.isTestActive = false;
    }

    restartTest() {
        this.isTestActive = false;
        this.isTestComplete = false;
        this.startTime = null;
        this.endTime = null;
        this.correctCharacters = 0;
        this.typedCharacters = 0;
        this.timeRemaining = this.testDuration;

        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }

        this.textInputElement.value = '';
        this.textInputElement.disabled = false;
        this.textInputElement.focus();
        
        this.updateStats();
        this.updateTimeLeft();
        this.renderQuoteWithProgress();
    }

    newQuote() {
        this.restartTest();
        this.displayRandomQuote();
    }

    updateStats() {
        this.wpmElement.textContent = this.calculateWPM();
        this.correctedWpmElement.textContent = this.calculateCorrectedWPM();
    }

    updateTimer() {
        if (!this.startTime) return;
        
        this.timeRemaining = Math.max(0, this.testDuration - Math.floor((Date.now() - this.startTime) / 1000));
        this.updateTimeLeft();
        
        if (this.timeRemaining <= 0) {
            this.completeTest();
        }
    }

    updateTimeLeft() {
        this.timeLeftElement.textContent = this.timeRemaining;
    }

    calculateWPM() {
        if (!this.startTime || !this.isTestActive) return 0;
        
        const elapsedMinutes = (Date.now() - this.startTime) / (1000 * 60);
        const correctWords = this.getCorrectWords();
        return Math.round(correctWords / elapsedMinutes) || 0;
    }

    calculateCorrectedWPM() {
        if (!this.startTime || !this.isTestActive) return 0;
        
        const elapsedMinutes = (Date.now() - this.startTime) / (1000 * 60);
        const correctWords = this.getCorrectWords();
        const accuracy = this.calculateAccuracy() / 100;
        return Math.round((correctWords * accuracy) / elapsedMinutes) || 0;
    }

    getCorrectWords() {
        const inputWords = this.textInputElement.value.trim().split(/\s+/);
        const quoteWords = this.currentQuote.trim().split(/\s+/);
        
        let correctWords = 0;
        for (let i = 0; i < Math.min(inputWords.length, quoteWords.length); i++) {
            if (inputWords[i] === quoteWords[i]) {
                correctWords++;
            }
        }
        return correctWords;
    }

    getTypedWords() {
        return this.textInputElement.value.trim().split(/\s+/).length;
    }

    calculateAccuracy() {
        const typedWords = this.getTypedWords();
        if (typedWords === 0) return 100;
        const correctWords = this.getCorrectWords();
        return Math.round((correctWords / typedWords) * 100);
    }

    updateBookSource() {
        if (this.currentBookTitle && this.currentBookLink) {
            const bookNumber = this.currentBookLink.replace('/', '');
            const bookUrl = `https://felixleger.com${this.currentBookLink}`;
            this.quoteSourceElement.innerHTML = `
                <div class="book-source">
                    Source : <a href="${bookUrl}" target="_blank" class="book-link">${this.currentBookTitle}</a>
                </div>
            `;
        }
    }
}

// Initialize the typing test when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new WPMTypingTest();
});