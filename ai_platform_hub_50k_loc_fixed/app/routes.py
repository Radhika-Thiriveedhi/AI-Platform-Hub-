"""Central route registration for AI Platform Hub."""
from __future__ import annotations

import re
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from data.mock_data import FAQ_ITEMS, FEATURES_LIST, TESTIMONIALS
from modules.analytics import get_dashboard_stats, get_top_models, get_usage_trends
from modules.blog import get_all_posts, get_categories as get_blog_categories, get_post_by_slug
from modules.chat_engine import clear_chat_history, get_chat_history, process_chat_message
from modules.docs import get_doc_page, get_docs_sections
from modules.image_gen import get_image_styles, get_recent_generations, generate_image, get_prompt_suggestions
from modules.models_catalog import get_all_models, get_categories, get_model_by_id, search_models
from modules.pricing import get_plan_details, get_pricing_plans
from modules.team import get_team_members
from modules.text_analysis import analyze_text, get_analysis_types
from services.ai_provider import provider_status
from services.database import add_contact, get_usage_summary, init_db


def register_blueprints(app):
    init_db()
    app.register_blueprint(main_bp)
    app.register_blueprint(models_bp, url_prefix="/models")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(image_bp, url_prefix="/image")
    app.register_blueprint(analysis_bp, url_prefix="/analysis")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(pricing_bp, url_prefix="/pricing")
    app.register_blueprint(docs_bp, url_prefix="/docs")
    app.register_blueprint(blog_bp, url_prefix="/blog")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pages_bp)


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("home.html", featured_models=get_all_models()[:6], stats=get_dashboard_stats(), features=FEATURES_LIST, testimonials=TESTIMONIALS)


@main_bp.route("/about")
def about():
    return render_template("about.html", team=get_team_members())


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    message = None
    category = "success"
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("message", "").strip()
        if not name or not body or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            message, category = "Please provide a valid name, email address, and message.", "error"
        elif len(body) > 5000:
            message, category = "Message is too long. Please keep it under 5,000 characters.", "error"
        else:
            ticket = add_contact(name, email, subject, body)
            message = f"Thanks {name}. Your support request #{ticket} has been recorded."
    return render_template("contact.html", message=message, message_category=category)


@main_bp.route("/features")
def features():
    return render_template("features.html", features=FEATURES_LIST)


@main_bp.route("/faq")
def faq():
    return render_template("faq.html", faqs=FAQ_ITEMS)


models_bp = Blueprint("models", __name__)


@models_bp.route("/")
def models_list():
    category = request.args.get("category", "all")
    query = request.args.get("q", "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    models = search_models(query) if query else get_all_models()
    if not query and category != "all":
        models = [m for m in models if m.get("category") == category]
    categories = get_categories()
    per_page = 12
    total = len(models)
    start = (page - 1) * per_page
    return render_template("models/list.html", models=models[start:start + per_page], categories=categories, current_category=category, query=query, page=page, total_pages=max(1, (total + per_page - 1) // per_page), total=total)


@models_bp.route("/<model_id>")
def model_detail(model_id):
    model = get_model_by_id(model_id)
    if not model:
        return render_template("errors/404.html"), 404
    related = [m for m in get_all_models() if m.get("category") == model.get("category") and m.get("id") != model_id][:4]
    return render_template("models/detail.html", model=model, related=related)


@models_bp.route("/compare")
def models_compare():
    ids = request.args.getlist("ids")
    models = [get_model_by_id(i) for i in ids if get_model_by_id(i)]
    return render_template("models/compare.html", models=models)


chat_bp = Blueprint("chat", __name__)


def _conversation_id() -> str:
    if "conversation_id" not in session:
        import secrets
        session["conversation_id"] = secrets.token_urlsafe(16)
    return session["conversation_id"]


@chat_bp.route("/")
def chat_interface():
    return render_template("chat/interface.html", history=get_chat_history(_conversation_id()), provider=provider_status())


@chat_bp.route("/send", methods=["POST"])
def chat_send():
    payload = request.get_json(silent=True) or {}
    message = request.form.get("message") or payload.get("message", "")
    result = process_chat_message(message, _conversation_id())
    return jsonify(result), (200 if result.get("status") == "success" else 400)


@chat_bp.route("/clear", methods=["POST"])
def chat_clear():
    clear_chat_history(_conversation_id())
    return redirect(url_for("chat.chat_interface"))


image_bp = Blueprint("image", __name__)


@image_bp.route("/")
def image_studio():
    return render_template("image/studio.html", styles=get_image_styles(), recent=get_recent_generations(), provider=provider_status(), suggestions=get_prompt_suggestions())


@image_bp.route("/generate", methods=["POST"])
def image_generate():
    payload = request.get_json(silent=True) or {}
    prompt = request.form.get("prompt") or payload.get("prompt", "")
    style = request.form.get("style") or payload.get("style", "realistic")
    size = request.form.get("size") or payload.get("size", "1024x1024")
    if size not in {"512x512", "1024x1024", "1536x1024", "1024x1536"}:
        size = "1024x1024"
    result = generate_image(prompt, style, size)
    return jsonify(result), (200 if result.get("status") == "success" else 400)


analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/")
def analysis_tools():
    return render_template("analysis/tools.html", analysis_types=get_analysis_types())


@analysis_bp.route("/run", methods=["POST"])
def analysis_run():
    payload = request.get_json(silent=True) or {}
    text = request.form.get("text") or payload.get("text", "")
    analysis_type = request.form.get("type") or payload.get("type", "sentiment")
    result = analyze_text(text, analysis_type)
    return jsonify(result), (200 if result.get("status") == "success" else 400)


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def dashboard_home():
    return render_template("dashboard/home.html", stats=get_dashboard_stats(), trends=get_usage_trends(), top_models=get_top_models())


@dashboard_bp.route("/usage")
def dashboard_usage():
    return render_template("dashboard/usage.html", trends=get_usage_trends())


pricing_bp = Blueprint("pricing", __name__)


@pricing_bp.route("/")
def pricing_plans():
    return render_template("pricing/plans.html", plans=get_pricing_plans())


@pricing_bp.route("/<plan_id>")
def pricing_detail(plan_id):
    plan = get_plan_details(plan_id)
    if not plan:
        return render_template("errors/404.html"), 404
    return render_template("pricing/detail.html", plan=plan)


docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/")
def docs_index():
    return render_template("docs/index.html", sections=get_docs_sections())


@docs_bp.route("/<section>/<page>")
def docs_page(section, page):
    content = get_doc_page(section, page)
    if not content:
        return render_template("errors/404.html"), 404
    return render_template("docs/page.html", content=content, sections=get_docs_sections(), current_section=section)


blog_bp = Blueprint("blog", __name__)


@blog_bp.route("/")
def blog_list():
    category = request.args.get("category", "all")
    posts = get_all_posts()
    if category != "all": posts = [p for p in posts if p.get("category") == category]
    return render_template("blog/list.html", posts=posts, categories=get_blog_categories(), current_category=category)


@blog_bp.route("/<slug>")
def blog_post(slug):
    post = get_post_by_slug(slug)
    if not post: return render_template("errors/404.html"), 404
    return render_template("blog/post.html", post=post)


api_bp = Blueprint("api", __name__)


@api_bp.route("/models")
def api_models(): return jsonify(get_all_models())


@api_bp.route("/models/<model_id>")
def api_model_detail(model_id):
    model = get_model_by_id(model_id)
    return (jsonify(model), 200) if model else (jsonify({"error":"Not found"}), 404)


@api_bp.route("/stats")
def api_stats(): return jsonify(get_dashboard_stats())


@api_bp.route("/usage")
def api_usage(): return jsonify(get_usage_summary())


@api_bp.route("/provider-status")
def api_provider_status(): return jsonify(provider_status())


@api_bp.route("/health")
def api_health():
    return jsonify({"status":"ok","service":"AI Platform Hub","version":"2.0.0","provider":provider_status()})


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/privacy")
def privacy(): return render_template("pages/privacy.html")


@pages_bp.route("/terms")
def terms(): return render_template("pages/terms.html")


@pages_bp.route("/careers")
def careers(): return render_template("pages/careers.html")


@pages_bp.route("/partners")
def partners(): return render_template("pages/partners.html")


@pages_bp.route("/changelog")
def changelog(): return render_template("pages/changelog.html")


@pages_bp.route("/status")
def status(): return render_template("pages/status.html", provider=provider_status())
