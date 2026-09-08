import { configureStore, createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { sessionStorageKeys } from "../api/client";

type AuthState = {
  adminToken: string | null;
  adminEmail: string | null;
  role: string | null;
  staffId: number | null;
};

const authSlice = createSlice({
  name: "auth",
  initialState: {
    adminToken: localStorage.getItem(sessionStorageKeys.admin),
    adminEmail: localStorage.getItem("mnp_admin_email"),
    role: null,
    staffId: null,
  } as AuthState,
  reducers: {
    signedIn(state, action: PayloadAction<{ token: string; email: string }>) {
      state.adminToken = action.payload.token;
      state.adminEmail = action.payload.email;
      localStorage.setItem("mnp_admin_email", action.payload.email);
    },
    signedOut(state) {
      state.adminToken = null;
      state.adminEmail = null;
      state.role = null;
      state.staffId = null;
      localStorage.removeItem(sessionStorageKeys.admin);
      localStorage.removeItem("mnp_admin_email");
    },
    staffVerified(state, action: PayloadAction<{id: number; role: string; email: string}>) {
      state.role = action.payload.role;
      state.staffId = action.payload.id;
      state.adminEmail = action.payload.email;
    },
  },
});

export const { signedIn, signedOut, staffVerified } = authSlice.actions;
export const store = configureStore({ reducer: { auth: authSlice.reducer } });
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
