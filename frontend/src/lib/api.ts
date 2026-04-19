const API_BASE_URL = "http://localhost:8030/api/v1";

interface ApiOptions extends RequestInit {
  email?: string;
}

export const fetchApi = async (endpoint: string, options: ApiOptions = {}) => {
  const { email, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});
  
  if (email) {
    headers.set("X-User-Email", email);
  }
  
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || response.statusText);
  }

  return response.json();
};

export const api = {
  auth: {
    register: (email: string) => fetchApi("/auth/register/", { 
      method: "POST", 
      body: JSON.stringify({ email }) 
    }),
    me: (email: string) => fetchApi(`/auth/me/?email=${email}`, { email }),
  },
  items: {
    search: (q: string) => fetchApi(`/items/search?q=${q}`),
  },
  aggregates: {
    list: (email: string) => fetchApi("/aggregates/", { email }),
    get: (email: string, id: string) => fetchApi(`/aggregates/${id}`, { email }),
    create: (email: string, data: any) => fetchApi("/aggregates/", {
      email,
      method: "POST",
      body: JSON.stringify(data),
    }),
    update: (email: string, id: string, data: any) => fetchApi(`/aggregates/${id}`, {
      email,
      method: "PUT",
      body: JSON.stringify(data),
    }),
    delete: (email: string, id: string) => fetchApi(`/aggregates/${id}`, {
      email,
      method: "DELETE",
    }),
  },
  shoppingLists: {
    list: (email: string) => fetchApi("/shopping-lists/", { email }),
    create: (email: string, data: any) => fetchApi("/shopping-lists/", {
      email,
      method: "POST",
      body: JSON.stringify(data),
    }),
  },
  optimization: {
    optimize: (email: string, data: any) => fetchApi("/optimize/", {
      email,
      method: "POST",
      body: JSON.stringify(data),
    }),
  },
};
