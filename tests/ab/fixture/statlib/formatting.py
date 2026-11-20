def format_text(summary):
    return "\n".join(f"{k}: {v:.4g}" for k, v in summary.items())
