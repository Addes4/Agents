from __future__ import annotations

from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from credit_committee.models import CommitteeRun, Deal

SLIDE_W = 12192000
SLIDE_H = 6858000
NAVY = "17365D"
GOLD = "B08A00"
TEXT = "222222"
MUTED = "666666"
LIGHT_BG = "F7F8FA"
PANEL_BG = "FFFFFF"
PANEL_BORDER = "D9DEE7"


def build_ic_memo_pptx(deal: Deal, run: CommitteeRun) -> bytes:
    slides = _slides_for_run(deal, run)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as package:
        _write_static_parts(package, len(slides))
        for index, (title, bullets) in enumerate(slides, start=1):
            package.writestr(
                f"ppt/slides/slide{index}.xml",
                _slide_xml(
                    title,
                    bullets,
                    slide_number=index,
                    slide_count=len(slides),
                    is_cover=index == 1,
                ),
            )
            package.writestr(
                f"ppt/slides/_rels/slide{index}.xml.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
            )
    return buffer.getvalue()


def _slides_for_run(deal: Deal, run: CommitteeRun) -> list[tuple[str, list[str]]]:
    scorecard = run.aggregate_scorecard
    chair = run.chair_synthesis
    first_views = run.agent_results
    challenges = run.challenge_results or []

    top_risks = _dedupe([item for result in first_views for item in result.concerns], 5)
    mitigants = _dedupe([item for result in first_views for item in (result.mitigants or [])], 5)
    diligence = _dedupe(
        (chair.gating_diligence if chair else [])
        + [item for result in first_views for item in (result.missing_diligence or [])],
        6,
    )
    conditions = _dedupe(
        (chair.approval_conditions if chair else [])
        + [item for result in first_views for item in result.conditions],
        6,
    )
    challenge_points = _dedupe([item for result in challenges for item in result.challenge_points], 6)

    recommendation = chair.final_advisory_recommendation if chair else "Defer"
    rationale = chair.committee_rationale if chair else "No chair rationale generated."
    scorecard_lines = (
        [
            f"Repayment capacity: {scorecard.repayment_capacity:.1f}/5",
            f"Downside resilience: {scorecard.downside_resilience:.1f}/5",
            f"Documentation quality: {scorecard.documentation_quality:.1f}/5",
            f"Sponsor support: {scorecard.sponsor_support:.1f}/5",
            f"Approval readiness: {scorecard.approval_readiness:.1f}/5",
            f"Lowest dimension: {scorecard.lowest_dimension or 'None'} ({scorecard.lowest_score:.1f}/5)",
        ]
        if scorecard
        else ["No aggregate scorecard saved."]
    )

    return [
        (
            f"Advisory IC Memo: {deal.borrower}",
            [
                f"Chair recommendation: {recommendation}",
                f"Sponsor: {deal.sponsor}",
                f"Sector/geography: {deal.sector} / {deal.geography}",
                f"Mode: {run.mode}",
                "Synthetic/demo output. Advisory only; humans make final decisions.",
            ],
        ),
        (
            "Executive Recommendation",
            [rationale],
        ),
        (
            "Credit Snapshot",
            [
                f"Revenue: {deal.revenue_m:.1f}m; EBITDA: {deal.ebitda_m:.1f}m",
                f"Debt: {deal.total_debt_m:.1f}m; leverage: {deal.leverage:.2f}x",
                f"EV / EBITDA: {deal.enterprise_value_multiple:.2f}x",
                f"Sponsor equity: {deal.sponsor_equity_m:.1f}m ({deal.sponsor_equity_percentage:.1%} of EV)",
                f"Pricing: {deal.pricing}",
            ],
        ),
        ("Scorecard", scorecard_lines),
        ("Top Risks", top_risks or ["None identified."]),
        ("Mitigants", mitigants or ["None identified."]),
        ("Challenge Round", challenge_points or ["No challenge points saved."]),
        ("Gating Diligence", diligence or ["None identified."]),
        ("Approval Conditions", conditions or ["None identified."]),
    ]


def _dedupe(items: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen[:limit]


def _write_static_parts(package: ZipFile, slide_count: int) -> None:
    overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, slide_count + 1)
    )
    package.writestr(
        "[Content_Types].xml",
        f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{overrides}
</Types>""",
    )
    package.writestr(
        "_rels/.rels",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>""",
    )
    slide_ids = "\n".join(
        f'<p:sldId id="{255 + index}" r:id="rId{index}"/>'
        for index in range(1, slide_count + 1)
    )
    package.writestr(
        "ppt/presentation.xml",
        f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{slide_count + 1}"/></p:sldMasterIdLst>
<p:sldIdLst>{slide_ids}</p:sldIdLst>
<p:sldSz cx="12192000" cy="6858000" type="wide"/>
<p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>""",
    )
    rels = "\n".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, slide_count + 1)
    )
    package.writestr(
        "ppt/_rels/presentation.xml.rels",
        f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{rels}
<Relationship Id="rId{slide_count + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
<Relationship Id="rId{slide_count + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
</Relationships>""",
    )
    package.writestr("ppt/slideMasters/slideMaster1.xml", _minimal_master_xml())
    package.writestr(
        "ppt/slideMasters/_rels/slideMaster1.xml.rels",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>""",
    )
    package.writestr("ppt/slideLayouts/slideLayout1.xml", _minimal_layout_xml())
    package.writestr(
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
    )
    package.writestr("ppt/theme/theme1.xml", _theme_xml())


def _slide_xml(
    title: str,
    bullets: list[str],
    slide_number: int,
    slide_count: int,
    is_cover: bool = False,
) -> str:
    if is_cover:
        content = _cover_shapes(title, bullets, slide_number, slide_count)
    elif title == "Credit Snapshot":
        content = _standard_chrome(title, slide_number, slide_count) + _metric_card_grid(bullets)
    else:
        content = _standard_chrome(title, slide_number, slide_count) + _body_panel(bullets)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
{_rect(2, "Background", 0, 0, SLIDE_W, SLIDE_H, LIGHT_BG)}
{content}
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def _cover_shapes(
    title: str,
    bullets: list[str],
    slide_number: int,
    slide_count: int,
) -> str:
    recommendation = bullets[0] if bullets else "Chair recommendation: Pending"
    meta = bullets[1:]
    return "\n".join(
        [
            _rect(3, "Cover band", 0, 0, SLIDE_W, 2800000, NAVY),
            _rect(4, "Gold accent", 0, 2800000, SLIDE_W, 70000, GOLD),
            _text_box(5, "Cover title", 720000, 660000, 10400000, 850000, title, 4000, "FFFFFF", True),
            _text_box(6, "Recommendation", 720000, 1650000, 7600000, 500000, recommendation, 2400, "FFFFFF", False),
            _body_panel(meta[:4], shape_id=7, x=720000, y=3350000, cx=10800000, cy=2100000),
            _footer(slide_number, slide_count, shape_id=20),
        ]
    )


def _standard_chrome(title: str, slide_number: int, slide_count: int) -> str:
    return "\n".join(
        [
            _rect(3, "Header", 0, 0, SLIDE_W, 720000, NAVY),
            _rect(4, "Accent", 0, 720000, SLIDE_W, 45000, GOLD),
            _text_box(5, "Slide title", 520000, 175000, 9300000, 350000, title, 2600, "FFFFFF", True),
            _footer(slide_number, slide_count, shape_id=30),
        ]
    )


def _body_panel(
    bullets: list[str],
    shape_id: int = 10,
    x: int = 640000,
    y: int = 1180000,
    cx: int = 10900000,
    cy: int = 5000000,
) -> str:
    body = "\n".join(_bullet_paragraph(item) for item in bullets[:7])
    return "\n".join(
        [
            _rect(shape_id, "Content panel", x, y, cx, cy, PANEL_BG, PANEL_BORDER),
            _text_shape(
                shape_id + 1,
                "Content",
                x + 300000,
                y + 260000,
                cx - 600000,
                cy - 520000,
                body or _bullet_paragraph("None identified."),
            ),
        ]
    )


def _metric_card_grid(items: list[str]) -> str:
    cards: list[str] = []
    x0 = 640000
    y0 = 1250000
    card_w = 3380000
    card_h = 1250000
    gap = 320000
    for index, item in enumerate(items[:6]):
        row = index // 3
        col = index % 3
        x = x0 + col * (card_w + gap)
        y = y0 + row * (card_h + 440000)
        title, value = _split_metric(item)
        shape_id = 10 + index * 4
        cards.extend(
            [
                _rect(shape_id, "Metric card", x, y, card_w, card_h, PANEL_BG, PANEL_BORDER),
                _rect(shape_id + 1, "Metric accent", x, y, 90000, card_h, GOLD),
                _text_box(shape_id + 2, "Metric label", x + 260000, y + 210000, card_w - 420000, 250000, title, 1500, MUTED, True),
                _text_box(shape_id + 3, "Metric value", x + 260000, y + 540000, card_w - 420000, 360000, value, 2100, TEXT, True),
            ]
        )
    return "\n".join(cards)


def _split_metric(text: str) -> tuple[str, str]:
    if ":" in text:
        title, value = text.split(":", 1)
        return title.strip(), value.strip()
    if ";" in text:
        title, value = text.split(";", 1)
        return title.strip(), value.strip()
    return "Metric", text


def _footer(slide_number: int, slide_count: int, shape_id: int) -> str:
    return "\n".join(
        [
            _rect(shape_id, "Footer line", 520000, 6350000, 11150000, 15000, PANEL_BORDER),
            _text_box(
                shape_id + 1,
                "Footer",
                520000,
                6420000,
                6400000,
                240000,
                "Private Credit Committee | Advisory draft",
                1100,
                MUTED,
                False,
            ),
            _text_box(
                shape_id + 2,
                "Slide number",
                10500000,
                6420000,
                1150000,
                240000,
                f"{slide_number} / {slide_count}",
                1100,
                MUTED,
                False,
            ),
        ]
    )


def _rect(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    fill: str,
    line: str | None = None,
) -> str:
    line_xml = (
        f'<a:ln><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        if line
        else "<a:ln><a:noFill/></a:ln>"
    )
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>{line_xml}</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>"""


def _text_box(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    text: str,
    size: int,
    color: str,
    bold: bool,
) -> str:
    bold_attr = ' b="1"' if bold else ""
    body = f"""<a:p><a:r><a:rPr lang="en-US" sz="{size}"{bold_attr}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:rPr><a:t>{escape(_shorten(text, 180))}</a:t></a:r></a:p>"""
    return _text_shape(shape_id, name, x, y, cx, cy, body)


def _text_shape(shape_id: int, name: str, x: int, y: int, cx: int, cy: int, body: str) -> str:
    return f"""<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{body}</p:txBody></p:sp>"""


def _bullet_paragraph(text: str) -> str:
    return f"""<a:p><a:pPr marL="260000" indent="-150000"><a:buChar char="•"/></a:pPr><a:r><a:rPr lang="en-US" sz="1850"><a:solidFill><a:srgbClr val="{TEXT}"/></a:solidFill></a:rPr><a:t>{escape(_shorten(text, 210))}</a:t></a:r></a:p>"""


def _shorten(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}..."


def _minimal_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""


def _minimal_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def _theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Credit Committee">
<a:themeElements><a:clrScheme name="Office"><a:dk1><a:srgbClr val="111111"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="333333"/></a:dk2><a:lt2><a:srgbClr val="F5F5F5"/></a:lt2><a:accent1><a:srgbClr val="2F5597"/></a:accent1><a:accent2><a:srgbClr val="70AD47"/></a:accent2><a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4><a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="C00000"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme><a:fontScheme name="Office"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements>
</a:theme>"""
