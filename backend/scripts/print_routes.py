from main import app

print("\n--- Registered Routes ---")
for route in app.routes:
    try:
        if hasattr(route, "path") and hasattr(route, "methods"):
            print(f"Path: {route.path}, Methods: {list(route.methods)}")
        elif hasattr(route, "routes"):  # For APIRouter, it has a list of sub-routes
            for sub_route in route.routes:
                if hasattr(sub_route, "path") and hasattr(sub_route, "methods"):
                    print(
                        f"Path: {route.prefix}{sub_route.path}, Methods: {list(sub_route.methods)}"
                    )
    except Exception as e:
        print(f"Error inspecting route: {e}, Route object: {route}")
print("---------------------------\n")
