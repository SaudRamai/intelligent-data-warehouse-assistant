PREMIUM_CSS = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
            html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
            h1, h2, h3, h4, h5, h6 { color: #002244 !important; }
            .glass-card {
                background: rgba(0, 34, 68, 0.8); /* Navy Blue Glass */
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                color: #FFFFFF; /* White text for dark cards */
            }
            .glass-card-white {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 34, 68, 0.1);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
                color: #002244; /* Navy Blue text for white cards */
            }
            .header-banner {
                background: rgba(0, 34, 68, 0.9); /* Deep Navy Glass */
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 20px;
                padding: 50px 40px;
                margin-bottom: 40px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            }
            .header-banner, .glass-card, .glass-card-white {
                position: relative;
                overflow: hidden;
            }
            .header-banner::after, .glass-card::after, .glass-card-white::after {
                content: "";
                position: absolute;
                top: -50%;
                left: -60%;
                width: 20%;
                height: 200%;
                background: rgba(255, 255, 255, 0.1);
                transform: rotate(30deg);
                animation: shine 4s infinite;
            }
            @keyframes shine {
                0% { left: -60%; }
                20% { left: 120%; }
                100% { left: 120%; }
            }
            .accent-text { color: #38BDF8; font-weight: 600; }
        </style>
"""
