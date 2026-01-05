from phone_agent.model.client import MessageBuilder


def test_message_builder():
    print("Testing MessageBuilder.create_user_message...")

    # Test 1: Valid image
    msg = MessageBuilder.create_user_message("test", "base64data" * 20)  # proper length
    has_image = any(item.get("type") == "image_url" for item in msg["content"])
    print(f"Valid image included: {has_image}")

    # Test 2: "None" string
    msg_none = MessageBuilder.create_user_message("test", "None")
    has_image_none = any(item.get("type") == "image_url" for item in msg_none["content"])
    print(f"'None' string excluded: {not has_image_none}")

    # Test 3: "None " string with space
    msg_none_space = MessageBuilder.create_user_message("test", "None ")
    has_image_none_space = any(
        item.get("type") == "image_url" for item in msg_none_space["content"]
    )
    print(f"'None ' string excluded: {not has_image_none_space}")

    # Test 4: Short string
    msg_short = MessageBuilder.create_user_message("test", "short")
    has_image_short = any(item.get("type") == "image_url" for item in msg_short["content"])
    print(f"Short string excluded: {not has_image_short}")


if __name__ == "__main__":
    test_message_builder()
