    // Service card hover-to-reveal
    document.querySelectorAll('.service-card.interactive, .price-card.interactive').forEach(card => {
        card.addEventListener('mouseenter', function() {
            card.classList.add('revealed');
        });
        card.addEventListener('mouseleave', function() {
            card.classList.remove('revealed');
        });
    });
// main.js - Modern JS features for Palmertech

document.addEventListener('DOMContentLoaded', () => {
    // Navbar underline animation
    document.querySelectorAll('.nav-list a').forEach(link => {
        link.addEventListener('mouseenter', e => {
            link.style.textDecoration = 'underline';
        });
        link.addEventListener('mouseleave', e => {
            link.style.textDecoration = 'none';
        });
    });

    // Swipe detection for interactive cards (touch devices)
    const interactiveCards = document.querySelectorAll('.service-card.interactive, .price-card.interactive');
    interactiveCards.forEach(card => {
        let startX = 0;
        card.addEventListener('touchstart', e => {
            startX = e.touches[0].clientX;
        });
        card.addEventListener('touchend', e => {
            let endX = e.changedTouches[0].clientX;
            if (endX - startX > 80) {
                card.classList.add('swiped-right');
            } else if (startX - endX > 80) {
                card.classList.add('swiped-left');
            }
            setTimeout(() => {
                card.classList.remove('swiped-right', 'swiped-left');
            }, 600);
        });
    });

    // Contact form client-side validation
    const contactForm = document.querySelector('.contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            const email = contactForm.querySelector('input[type="email"]');
            if (!email.value.includes('@')) {
                e.preventDefault();
                alert('Please enter a valid email address.');
            }
        });
    }

    const modal = document.getElementById('portfolioPreviewModal');
    if (modal) {
        const frame = modal.querySelector('iframe');
        const titleEl = modal.querySelector('.portfolio-modal-title');
        const closeBtn = modal.querySelector('.portfolio-modal-close');

        const closeModal = () => {
            modal.setAttribute('hidden', '');
            frame.src = '';
            document.body.classList.remove('modal-open');
        };

        const openModal = (url, title) => {
            frame.src = url;
            titleEl.textContent = title;
            modal.removeAttribute('hidden');
            document.body.classList.add('modal-open');
        };

        document.querySelectorAll('.preview-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const url = btn.dataset.previewUrl;
                const title = btn.dataset.previewTitle || 'Project preview';
                openModal(url, title);
            });
        });

        closeBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', event => {
            if (event.target === modal) {
                closeModal();
            }
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && !modal.hasAttribute('hidden')) {
                closeModal();
            }
        });
    }
});
