output "storage_account_name" {
  value = azurerm_storage_account.datalake.name
}

output "sql_server_fqdn" {
  value = azurerm_mssql_server.main.fully_qualified_domain_name
}