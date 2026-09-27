# Security boundary

The backend is the authoritative authorization boundary. This package is reserved for Entra token validation, Graph group resolution/cache, role mapping, and element-level authorization.

Those integrations are intentionally not implemented in the backend foundation scaffold. Until the security implementation is added, protected routes must fail closed rather than infer authorization from client-provided data.
