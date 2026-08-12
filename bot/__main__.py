"""Main entry point for the bot."""
from bot.handlers import create_application


def main():
    """Start the bot."""
    print("🚀 Starting Telegram Sender Bot...")
    print("Press Ctrl+C to stop")
    
    application = create_application()
    
    # Run the bot
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
