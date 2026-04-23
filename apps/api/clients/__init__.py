"""
Clients module.

Manages client (patients/customers) for each professional.
Handles CRUD operations, search, and client-related business logic.

This module is tenant-isolated via RLS - each professional can only
access their own clients.
"""
