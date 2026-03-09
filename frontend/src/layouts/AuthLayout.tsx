import { Outlet } from 'react-router-dom';
import { Layout, Row, Col, Typography } from 'antd';
import { Mic } from 'lucide-react';

const { Content } = Layout;
const { Title, Paragraph } = Typography;

export default function AuthLayout() {
  return (
    <Layout className="min-h-screen">
      <Content>
        <Row className="min-h-screen">
          <Col xs={0} md={12} lg={14} className="bg-gradient-to-br from-indigo-900 to-indigo-600 flex flex-col justify-center items-center text-white p-12">
            <div className="max-w-lg text-left">
              <Mic className="h-16 w-16 mb-6 text-indigo-300" />
              <Title level={1} className="!text-white mb-4">Master Your Speaking Skills</Title>
              <Paragraph className="text-indigo-100 text-lg">
                Practice with multi-provider LLMs, engage in real-time conversations, and receive comprehensive evaluation scoring to improve your communication.
              </Paragraph>
            </div>
          </Col>
          <Col xs={24} md={12} lg={10} className="flex flex-col justify-center items-center bg-gray-50 p-6 sm:p-12">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
              <div className="flex justify-center mb-6 md:hidden">
                <Mic className="h-10 w-10 text-indigo-600" />
              </div>
              <Title level={2} className="text-center mb-6 !text-indigo-700 md:hidden">
                Speaking App
              </Title>
              <Outlet />
            </div>
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}
