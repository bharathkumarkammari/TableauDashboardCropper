import requests
import logging
from typing import Dict, List, Tuple, Optional

class TableauAPI:
    def __init__(self, server_url: str, site_id: str):
        self.server_url = server_url.rstrip('/')
        self.site_id = site_id
        self.token = None
        self.site_id_response = None
        self.user_id = None
        self.api_version = "3.20"
    
    def authenticate(self, username: str, password: str) -> Tuple[str, str, str]:
        """Authenticate with Tableau Server and return token, site_id, user_id"""
        url = f"{self.server_url}/api/{self.api_version}/auth/signin"
        
        payload = {
            "credentials": {
                "name": username,
                "password": password,
                "site": {"contentUrl": self.site_id}
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            logging.info(f"Attempting authentication for user: {username} on site: {self.site_id}")
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            self.token = data['credentials']['token']
            self.site_id_response = data['credentials']['site']['id']
            self.user_id = data['credentials']['user']['id']
            
            logging.info(f"Successfully authenticated user: {username}")
            logging.info(f"Received site_id: {self.site_id_response}")
            logging.info(f"Received token: {self.token[:20]}...")
            
            return self.token, self.site_id_response, self.user_id
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Authentication failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('detail', str(e))
                except:
                    error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
                raise Exception(f"Tableau authentication failed: {error_msg}")
            else:
                raise Exception(f"Network error during authentication: {str(e)}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token"""
        if not self.token:
            raise Exception("Not authenticated. Please call authenticate() first.")
        
        return {
            "X-Tableau-Auth": self.token,
            "Accept": "application/json"
        }
    
    def get_projects(self) -> List[Dict]:
        """Get all projects accessible to the authenticated user"""
        if not self.site_id_response:
            raise Exception("No site ID available. Please authenticate first.")
            
        url = f"{self.server_url}/api/{self.api_version}/sites/{self.site_id_response}/projects"
        
        try:
            logging.info(f"Requesting projects from: {url}")
            response = requests.get(url, headers=self._get_headers())
            
            logging.info(f"Projects response status: {response.status_code}")
            if response.status_code != 200:
                logging.error(f"Projects response text: {response.text}")
            
            response.raise_for_status()
            
            data = response.json()
            logging.info(f"Projects response data: {data}")
            
            projects = data.get("projects", {}).get("project", [])
            
            # Ensure projects is always a list
            if isinstance(projects, dict):
                projects = [projects]
            
            logging.info(f"Retrieved {len(projects)} projects")
            for project in projects[:3]:  # Log first 3 projects for debugging
                logging.info(f"Project: {project.get('name', 'Unknown')} (ID: {project.get('id', 'Unknown')})")
            
            return projects
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to get projects: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response status: {e.response.status_code}")
                logging.error(f"Response text: {e.response.text}")
            raise Exception(f"Failed to retrieve projects: {str(e)}")
    
    def list_workbooks_in_project(self, project_name: str) -> List[Dict]:
        """Get all workbooks in a specific project"""
        try:
            # First get the project ID
            projects = self.get_projects()
            project_id = None
            
            for project in projects:
                if project['name'].lower() == project_name.lower():
                    project_id = project['id']
                    break
            
            if not project_id:
                logging.warning(f"Project '{project_name}' not found")
                return []
            
            # Get all workbooks
            url = f"{self.server_url}/api/{self.api_version}/sites/{self.site_id_response}/workbooks"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            all_workbooks = data.get("workbooks", {}).get("workbook", [])
            
            # Ensure workbooks is always a list
            if isinstance(all_workbooks, dict):
                all_workbooks = [all_workbooks]
            
            # Filter workbooks by project
            project_workbooks = []
            for wb in all_workbooks:
                if wb.get('project', {}).get('id') == project_id:
                    project_workbooks.append(wb)
            
            logging.info(f"Retrieved {len(project_workbooks)} workbooks for project '{project_name}'")
            return project_workbooks
            
        except Exception as e:
            logging.error(f"Failed to get workbooks for project '{project_name}': {str(e)}")
            raise Exception(f"Failed to retrieve workbooks: {str(e)}")
    
    def get_views_in_workbook(self, workbook_id: str) -> List[Dict]:
        """Get all views (dashboards) in a specific workbook"""
        url = f"{self.server_url}/api/{self.api_version}/sites/{self.site_id_response}/workbooks/{workbook_id}/views"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            views = data.get("views", {}).get("view", [])
            
            # Ensure views is always a list
            if isinstance(views, dict):
                views = [views]
            
            logging.info(f"Retrieved {len(views)} views for workbook {workbook_id}")
            return views
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to get views for workbook {workbook_id}: {str(e)}")
            raise Exception(f"Failed to retrieve dashboards: {str(e)}")
    
    def export_view_as_pdf(self, view_id: str) -> bytes:
        """Export a view as PDF and return the content"""
        url = f"{self.server_url}/api/{self.api_version}/sites/{self.site_id_response}/views/{view_id}/pdf"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            logging.info(f"Successfully exported view {view_id} as PDF")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to export view {view_id} as PDF: {str(e)}")
            raise Exception(f"Failed to export dashboard as PDF: {str(e)}")
    
    def sign_out(self):
        """Sign out and invalidate the authentication token"""
        if not self.token:
            return
        
        url = f"{self.server_url}/api/{self.api_version}/auth/signout"
        
        try:
            response = requests.post(url, headers=self._get_headers())
            response.raise_for_status()
            logging.info("Successfully signed out")
            
        except requests.exceptions.RequestException as e:
            logging.warning(f"Error during sign out: {str(e)}")
        
        finally:
            self.token = None
            self.site_id_response = None
            self.user_id = None
