"""
The six sections of the Brief Introduction to RNL.

The text lives here, on the server, and is handed out only to a verified member who has
unlocked that section. It is deliberately not part of portal.html, so nobody can read ahead
by opening the page source or guessing a web address.
"""

SECTIONS = [
    {
        "slug": 'who',
        "title": 'Who we are',
        "html": (
            '<p class="lead">Repellano Nigeria Limited (RNL) is an uncommon provider of financial support services, built on a “zero-risk” philosophy.</p>'
            '<p>We never charge you fees upfront and never trade with your money. We trade with our own capital: any profit we generate is ours, and a share of it is gifted to you as a cash loan.</p>'
            '<div class="note"><p>To secure your $10 starter loan, you place a refundable $10 security deposit in escrow with a third-party processor. RNL never collects it.</p>'
            '</div>'
            '<p style="margin-top:22px">We are politically neutral and do not promote any political cause. We also do not, and cannot, have all the solutions to human needs.</p>'
        ),
    },
    {
        "slug": 'structure',
        "title": 'Corporate structure and leadership',
        "html": (
            '<p class="lead">We are led by 62 visionaries.</p>'
            '<div class="leaders"><div class="leader"><div class="mini lit">1</div>'
            '<small>Group Managing Director</small></div>'
            '<div class="leader"><div class="mini">11</div>'
            '<small>Executive Directors</small></div>'
            '<div class="leader"><div class="mini">50</div>'
            '<small>CEOs</small></div>'
            '</div>'
            '<p>This fairly 1:5 leadership ratio ensures precision and top-level oversight.</p>'
            '<p>Each of them brings a wealth of experience and wisdom to ensure clinical delivery of the Sanctuary’s promises.</p>'
        ),
    },
    {
        "slug": 'digital',
        "title": 'Digital infrastructure and automation',
        "html": (
            '<p class="lead">The Repellano Digital Sanctuary is built on native Telegram, so profiling, onboarding and every service happen right here in your chat.</p>'
            '<ul class="principles"><li>Protective</li><li>Defensive</li><li>Anti-predatory</li><li>Integrated</li></ul>'
            '<p>Automation delivers each service with speed and surgical precision.</p>'
        ),
    },
    {
        "slug": 'fssos',
        "title": 'Financial Support Service Offerings',
        "html": (
            '<div class="count">35</div>'
            '<p class="lead">specialised Financial Support Service Offerings (FSSOs).</p>'
            '<div class="fssos" id="fssoGrid" aria-hidden="true"></div>'
            '<p style="margin-top:18px">Each FSSO is a precision-engineered tool that solves a specific financial need.</p>'
        ),
    },
    {
        "slug": 'started',
        "title": 'How we help you get started',
        "html": (
            '<ol class="path"><li>We give you a <b>$10 loan</b> to trade forex.</li><li>We give you our <b>automated trading system</b>.</li><li>If a trade ends in a loss, we give you another $10 loan for the next trade, and we repeat this until a trade wins.</li><li>A winning trade produces <b>$150</b> for you. Walk away with it, no questions asked, or use all or part of it to make more.</li></ol>'
            '<p>You get this solid foundation only once in your lifetime.</p>'
            '<div class="note"><p>Your $10 security deposit comes back to you on your first WIN, or if you walk away after a LOSS.</p>'
            '</div>'
        ),
    },
    {
        "slug": 'advice',
        "title": 'Our advice to you',
        "html": (
            '<blockquote>Decide wisely what to do with your earnings.</blockquote>'
            '<p class="lead">Always remember that the cash is a loan given to you, and RNL will never ask for it back.</p>'
        ),
    },
]

TOTAL = len(SECTIONS)
