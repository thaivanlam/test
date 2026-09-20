import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { queryClient } from "@/lib/queryClient";
import { useLogout, fetchCurrentUser } from "../api/auth";

export function useAuth() {
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const token = localStorage.getItem("access_token");
  const isAuthenticated = !!token;

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: isAuthenticated,
    retry: false,
  });

  // The query client is a module singleton, so it outlives the route change on
  // logout. Without clearing it, the cached ["currentUser"] and ["todos"]
  // entries stay fresh for staleTime and are handed to whoever logs in next in
  // the same tab.
  const logout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        navigate("/login");
        queryClient.clear();
      },
      onError: () => {
        // Even on error, clear local tokens and redirect
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        navigate("/login");
        queryClient.clear();
      },
    });
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    logout,
  };
}
