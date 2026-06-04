PREMIUM_CSS = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
            html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
            h1, h2, h3, h4, h5, h6 { color: #0f172a !important; font-family: 'Outfit', sans-serif; }
            
            /* Background subtle animated mesh */
            .stApp {
                background: radial-gradient(circle at 15% 50%, rgba(0, 109, 168, 0.04), transparent 25%),
                            radial-gradient(circle at 85% 30%, rgba(140, 28, 20, 0.06), transparent 25%);
            }

            .glass-card {
                background: linear-gradient(135deg, rgba(28, 72, 119, 0.95), rgba(10, 95, 150, 0.95));
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 20px;
                padding: 28px;
                box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.5);
                color: #f8fafc;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            .glass-card-white {
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(248, 250, 252, 0.95));
                backdrop-filter: blur(12px);
                border: 1px solid rgba(226, 232, 240, 0.8);
                border-radius: 20px;
                padding: 32px 28px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
                color: #0f172a;
                transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                cursor: pointer;
                position: relative;
                top: 0;
            }
            .glass-card-white:hover {
                transform: translateY(-8px) scale(1.02);
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1), 0 0 20px rgba(140, 28, 20, 0.15);
                border-color: rgba(140, 28, 20, 0.6);
            }
            .glass-card-white h3 {
                color: #0f172a;
                font-weight: 700;
                letter-spacing: -0.5px;
                margin-bottom: 12px;
            }
            
            .header-banner {
                background: linear-gradient(135deg, #0a5f96 0%, #1c4877 100%);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 24px;
                padding: 60px 50px;
                margin-bottom: 40px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                position: relative;
                overflow: hidden;
            }
            
            /* Animated gradient text for highlight */
            .text-gradient {
                background: linear-gradient(to right, #38bdf8, #ff4747, #38bdf8, #ff4747);
                background-size: 200% auto;
                color: transparent;
                -webkit-background-clip: text;
                background-clip: text;
                animation: gradient 4s linear infinite;
                font-weight: 800;
                text-shadow: 0 0 20px rgba(255, 71, 71, 0.4);
            }
            
            @keyframes gradient {
                0% { background-position: 0% center; }
                100% { background-position: 200% center; }
            }

            .header-banner::after, .glass-card::after, .glass-card-white::after {
                content: "";
                position: absolute;
                top: -50%;
                left: -60%;
                width: 20%;
                height: 200%;
                background: rgba(255, 255, 255, 0.05);
                transform: rotate(30deg);
                animation: shine 6s infinite;
            }
            .glass-card-white::after {
                background: rgba(255, 255, 255, 0.5);
            }
            @keyframes shine {
                0% { left: -60%; }
                20% { left: 120%; }
                100% { left: 120%; }
            }
            
            /* Primary Button Enhancement with Continuous Breathing Glow */
            @keyframes breathe-red {
                0% { box-shadow: 0 4px 15px rgba(183, 51, 39, 0.4); }
                50% { box-shadow: 0 4px 25px rgba(183, 51, 39, 0.9), 0 0 12px rgba(183, 51, 39, 0.6); }
                100% { box-shadow: 0 4px 15px rgba(183, 51, 39, 0.4); }
            }
            
            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #b73327, #8c1c14) !important;
                color: #ffffff !important;
                border: 1px solid rgba(255, 255, 255, 0.2) !important;
                border-radius: 12px !important;
                font-weight: 600 !important;
                letter-spacing: 0.5px !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                animation: breathe-red 3s infinite ease-in-out !important;
            }
            .stButton > button[kind="primary"]:hover {
                transform: translateY(-3px) scale(1.02);
                box-shadow: 0 12px 25px -3px rgba(183, 51, 39, 0.9), 0 0 20px rgba(183, 51, 39, 0.7) !important;
                animation: none !important;
            }
            
            .accent-text { color: #ff4747; font-weight: 600; }
            
            /* Pulsing effect for indicators */
            @keyframes pulse-red {
                0% { box-shadow: 0 0 0 0 rgba(140, 28, 20, 0.7); }
                70% { box-shadow: 0 0 0 10px rgba(140, 28, 20, 0); }
                100% { box-shadow: 0 0 0 0 rgba(140, 28, 20, 0); }
            }
            .status-offline {
                color: #8c1c14;
                animation: pulse-red 2s infinite;
                border-radius: 50%;
                display: inline-block;
            }
        </style>
"""
