document.addEventListener('DOMContentLoaded', function() {
    // Installation tabs functionality
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked button
            button.classList.add('active');
            
            // Get the tab to show
            const tabToShow = button.getAttribute('data-tab');
            
            // Show the corresponding tab content
            document.getElementById(`${tabToShow}-tab`).classList.add('active');
        });
    });
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 70, // Adjust for header height
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Highlight code blocks (simple version)
    document.querySelectorAll('.code-block code').forEach(block => {
        // Add simple syntax highlighting for terminal commands
        const content = block.innerHTML;
        block.innerHTML = content
            .replace(/\$\s(.+)/g, '<span style="color: #f8f8f2;">$ <span style="color: #a6e22e;">$1</span></span>')
            .replace(/(#.+)/g, '<span style="color: #75715e;">$1</span>');
    });
    
    // Animation for feature cards
    const featureCards = document.querySelectorAll('.feature-card');
    let delay = 0;
    
    featureCards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, delay);
        
        delay += 100;
    });
    
    // Simulate typing effect in the demo section
    const demoMessages = document.querySelectorAll('.chat-message p:first-child');
    const messageDelay = 1000;
    
    demoMessages.forEach((message, index) => {
        const originalText = message.textContent;
        message.textContent = '';
        
        setTimeout(() => {
            let i = 0;
            const typingInterval = setInterval(() => {
                message.textContent += originalText[i];
                i++;
                
                if (i >= originalText.length) {
                    clearInterval(typingInterval);
                }
            }, 30);
        }, messageDelay * index);
    });
});
